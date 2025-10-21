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
