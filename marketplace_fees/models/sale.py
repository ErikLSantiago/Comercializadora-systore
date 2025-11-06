# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_marketplace_fee = fields.Boolean(string="Es Fee de Marketplace", default=False, index=True)
    fee_type = fields.Selection(
        [("commission", "Comisión"), ("shipping", "Envío")],
        string="Tipo de Fee",
        default=False,
        index=True,
    )
    source_line_id = fields.Many2one("sale.order.line", string="Línea origen", ondelete="set null")
    fee_account_id = fields.Many2one("account.account", string="Cuenta contable (fee)")
    marketplace_channel_model = fields.Char(string="Modelo Marketplace")
    marketplace_channel_res_id = fields.Integer(string="ID Registro Marketplace")

    def _prepare_invoice_line(self, **optional_values):
        self.ensure_one()
        res = super()._prepare_invoice_line(**optional_values)

        # Fee: forzar cuenta de gasto si está definida.
        if self.is_marketplace_fee and self.fee_account_id:
            res["account_id"] = self.fee_account_id.id
            return res

        # Línea de venta: sobreescribir cuenta de ingresos si la config lo indica.
        if not self.is_marketplace_fee and self.product_id:
            order = self.order_id
            if order:
                channel = order._get_marketplace_channel_from_order()
                if channel:
                    config = order._find_product_channel_config(self.product_id.product_tmpl_id, channel)
                    if config and config.revenue_account_id:
                        account = config.revenue_account_id
                        fpos = order.fiscal_position_id or order.partner_id.property_account_position_id
                        if fpos:
                            account = fpos.map_account(account)
                        if account:
                            res["account_id"] = account.id
        return res


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # === Contacto para facturación por marketplace ===
    def _compute_single_billing_partner(self, channel):
        """Devuelve un partner único si todas las líneas de producto configuradas
        para el canal resuelven al mismo 'billing_partner_id'. Si no, False.
        """
        self.ensure_one()
        partner_ids = set()
        for line in self.order_line.filtered(lambda l: not getattr(l, "is_marketplace_fee", False) and not l.display_type and l.product_id):
            cfg = self._find_product_channel_config(line.product_id.product_tmpl_id, channel)
            if cfg and cfg.billing_partner_id:
                partner_ids.add(cfg.billing_partner_id.id)
        if len(partner_ids) == 1:
            return self.env["res.partner"].browse(list(partner_ids)[0])
        return False

    def _apply_billing_partner_if_needed(self):
        """Si la orden es de Producteca y todas las líneas configuradas coinciden
        en el mismo 'billing_partner_id', setea partner_invoice_id a ese partner.
        No sobreescribe si el usuario/flujo ya lo cambió a ese mismo valor.
        """
        for order in self:
            if order.env.context.get("marketplace_fees_set_inv"):
                continue
            channel = order._get_marketplace_channel_from_order()
            if not channel:
                continue
            partner = order._compute_single_billing_partner(channel)
            if partner and order.partner_invoice_id.id != partner.id:
                try:
                    # Verifica acceso del usuario actual y que name_get funcione
                    partner.with_user(order.env.user).name_get()
                    # Exigir misma empresa comercial para respetar dominios de la vista (evita KeyError)
                    cp_ok = True
                    try:
                        cp_ok = (partner.commercial_partner_id.id == order.partner_id.commercial_partner_id.id)
                    except Exception:
                        cp_ok = True  # si no se puede evaluar, no bloqueamos
                    if cp_ok:
                        order.with_context(marketplace_fees_set_inv=True).write({"partner_invoice_id": partner.id})
                    else:
                        order.message_post(body=f"[marketplace_fees] Contacto de facturación omitido por diferente empresa comercial: {partner.display_name}")
                except Exception as e:
                    order.message_post(body=f"[marketplace_fees] No se pudo aplicar el contacto de facturación '{partner.display_name}': {e}")

    def _is_producteca_order(self):
        """Detecta si la orden proviene de Producteca (binding/canal presente)."""
        self.ensure_one()
        # Campo computado de producteca: producteca_channel_binding
        if hasattr(self, "producteca_channel_binding") and self.producteca_channel_binding:
            return True
        # Algunas instalaciones usan producteca_bindings o producteca_sale_order
        if hasattr(self, "producteca_bindings") and getattr(self, "producteca_bindings"):
            return True
        if hasattr(self, "producteca_sale_order") and getattr(self, "producteca_sale_order"):
            return True
        return False

    def _draft_has_product_lines(self):
        self.ensure_one()
        return bool(self.order_line.filtered(lambda l: not getattr(l, "is_marketplace_fee", False) and not l.display_type and l.product_id))

    def _maybe_autoconfirm_producteca(self):
        """Autoconfirma órdenes de Producteca en estado borrador, de forma segura y sin romper flujos nativos."""
        for order in self:
            if order.state in ("draft", "sent") and order._is_producteca_order() and order._draft_has_product_lines():
                # Evitar loops y confirmar con el usuario que ejecuta la importación
                ctx = dict(self.env.context or {}, marketplace_fees_autoconfirm=True)
                try:
                    order.with_context(ctx).action_confirm()
                except Exception as e:
                    # No abortar el flujo de importación; solo registrar.
                    order.message_post(body=f"[marketplace_fees] No se pudo confirmar automáticamente: {e}")
                    # continuar sin bloquear

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        # Intentar después de crear (muchas integraciones crean líneas en el create)
        recs._apply_billing_partner_if_needed()
        recs._maybe_autoconfirm_producteca()
        return recs

    def write(self, vals):
        res = super().write(vals)
        # Aplicar partner de facturación antes de autoconfirmar
        self._apply_billing_partner_if_needed()
        # Evitar reentradas cuando la propia confirmación escribe sobre la orden
        if not self.env.context.get("marketplace_fees_autoconfirm"):
            self._maybe_autoconfirm_producteca()
        return res

    def action_confirm(self):
        # Agregar fees antes de confirmar; conservar flujo nativo.
        self._add_marketplace_fee_lines()
        return super().action_confirm()

    def _get_marketplace_channel_from_order(self):
        self.ensure_one()
        channel = getattr(self, "channel_binding_id", False)
        if not channel:
            channel = getattr(self, "producteca_channel_binding", False)
        return channel

    def _iter_possible_channel_targets(self, channel):
        if not channel:
            return
        yield (channel._name, channel.id)
        base = getattr(channel, "channel_id", False) or getattr(channel, "channel", False)
        if base:
            yield (base._name, base.id)

    def _get_base_producteca_channel(self, channel):
        if not channel:
            return False
        if channel._name == "producteca.channel":
            return channel
        base = getattr(channel, "channel_id", False) or getattr(channel, "channel", False)
        return base if getattr(base, "_name", "") == "producteca.channel" else False

    def _find_product_channel_config(self, tmpl, channel):
        if not channel:
            return tmpl.env["product.marketplace.fee.config"]
        cfgs = tmpl.marketplace_fee_config_ids
        base_channel = self._get_base_producteca_channel(channel)
        if base_channel:
            cfg = cfgs.filtered(lambda c: c.producteca_channel_id and c.producteca_channel_id.id == base_channel.id)[:1]
            if cfg:
                return cfg
        possible = set("%s,%s" % (m, i) for (m, i) in self._iter_possible_channel_targets(channel))
        return cfgs.filtered(lambda c: c.channel_ref and ("%s,%s" % (c.channel_ref._name, c.channel_ref.id)) in possible)[:1]

    def _add_marketplace_fee_lines(self):
        for order in self:
            channel = order._get_marketplace_channel_from_order()
            if not channel:
                continue
            product_lines = order.order_line.filtered(lambda l: not l.is_marketplace_fee and not l.display_type and l.product_id)
            for line in product_lines:
                tmpl = line.product_id.product_tmpl_id
                config = self._find_product_channel_config(tmpl, channel)
                if not config:
                    continue
                currency = order.currency_id
                company = order.company_id
                base_amount = line.price_unit * line.product_uom_qty * (1 - (line.discount or 0.0) / 100.0)
                commission_amount = currency.round(base_amount * (config.commission_percent or 0.0) / 100.0)
                shipping_unit = config.shipping_cost or 0.0
                if config.currency_id and config.currency_id != currency:
                    shipping_unit = config.currency_id._convert(shipping_unit, currency, company, order.date_order or fields.Date.context_today(order))
                shipping_amount = currency.round(shipping_unit * line.product_uom_qty)

                # Importes negativos para gastos.
                commission_amount = -abs(commission_amount) if commission_amount else 0.0
                shipping_amount = -abs(shipping_amount) if shipping_amount else 0.0

                channel_name = getattr(channel, "display_name", str(channel))
                common_vals = {
                    "order_id": order.id,
                    "product_uom_qty": 1.0,
                    "source_line_id": line.id,
                    "marketplace_channel_model": channel._name,
                    "marketplace_channel_res_id": channel.id,
                    "is_marketplace_fee": True,
                }

                if commission_amount:
                    existing_comm = order.order_line.filtered(lambda l: l.is_marketplace_fee and l.fee_type == "commission" and l.source_line_id.id == line.id)[:1]
                    vals_comm = dict(common_vals, **{
                        "product_id": config.commission_product_id.id,
                        "name": _("Comisión %(channel)s - %(prod)s", channel=channel_name, prod=line.product_id.display_name),
                        "price_unit": commission_amount,
                        "tax_id": [(6, 0, config.commission_product_id.taxes_id.ids)],
                        "fee_type": "commission",
                        "fee_account_id": config.commission_account_id.id if config.commission_account_id else False,
                    })
                    if existing_comm:
                        existing_comm.write({"price_unit": commission_amount})
                    else:
                        order.order_line.create(vals_comm)
                if shipping_amount:
                    existing_ship = order.order_line.filtered(lambda l: l.is_marketplace_fee and l.fee_type == "shipping" and l.source_line_id.id == line.id)[:1]
                    vals_ship = dict(common_vals, **{
                        "product_id": config.shipping_product_id.id,
                        "name": _("Envío %(channel)s - %(prod)s", channel=channel_name, prod=line.product_id.display_name),
                        "price_unit": shipping_amount,
                        "tax_id": [(6, 0, config.shipping_product_id.taxes_id.ids)],
                        "fee_type": "shipping",
                        "fee_account_id": config.shipping_account_id.id if config.shipping_account_id else False,
                    })
                    if existing_ship:
                        existing_ship.write({"price_unit": shipping_amount})
                    else:
                        order.order_line.create(vals_ship)
