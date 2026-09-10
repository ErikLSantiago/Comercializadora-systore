# -*- coding: utf-8 -*-
from odoo import models, api

class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_producteca_channel_binding(self):
        """Devuelve producteca.channel.binding asociado a la orden, si existe.

        - Algunos setups tienen sale.order.channel_binding_id directo.
        - En el conector Producteca que compartiste, la orden tiene producteca_bindings (M2M) hacia producteca.sale_order,
          y ahí existe channel_binding_id.
        """
        self.ensure_one()

        # Caso A: campo directo en sale.order (si existe por personalización)
        channel = getattr(self, "channel_binding_id", False) or getattr(self, "producteca_channel_binding", False)
        if channel:
            return channel

        # Caso B: conector Producteca: producteca_bindings -> producteca.sale_order -> channel_binding_id
        bindings = getattr(self, "producteca_bindings", False)
        if bindings:
            try:
                pso = bindings[0]
                channel = getattr(pso, "channel_binding_id", False)
                if channel:
                    return channel
            except Exception:
                return False

        # Caso C: campo compute producteca_sale_order (no store) si existiera
        pso = getattr(self, "producteca_sale_order", False)
        if pso:
            channel = getattr(pso, "channel_binding_id", False)
            if channel:
                return channel

        return False

    def _get_marketplace_billing_config(self):
        self.ensure_one()
        channel_binding = self._get_producteca_channel_binding()
        if not channel_binding:
            return False
        return self.env["marketplace.billing.config"].search([
            ("company_id", "=", self.company_id.id),
            ("active", "=", True),
            ("channel_binding_id", "=", channel_binding.id),
        ], limit=1)

    def _apply_marketplace_billing_config(self):
        for order in self:
            cfg = order._get_marketplace_billing_config()
            if cfg and cfg.invoice_partner_id:
                if order.partner_invoice_id.id != cfg.invoice_partner_id.id:
                    order.partner_invoice_id = cfg.invoice_partner_id

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._apply_marketplace_billing_config()
        return orders

    def write(self, vals):
        res = super().write(vals)
        # Re-aplicar si se modificó el canal/relaciones de Producteca o partner
        if any(k in vals for k in ("channel_binding_id", "producteca_channel_binding", "producteca_bindings")):
            self._apply_marketplace_billing_config()
        return res


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _prepare_invoice_line(self, **optional_values):
        vals = super()._prepare_invoice_line(**optional_values)
        order = self.order_id
        cfg = order._get_marketplace_billing_config() if order else False
        if cfg and cfg.income_account_id:
            vals["account_id"] = cfg.income_account_id.id
        return vals

def read(self, fields=None, load='_classic_read'):
    """Evita crashes del web client (KeyError) cuando algún many2one apunta a un registro no legible.

    Esto pasa típicamente en multi-compañía / record rules: el ID existe en BD,
    pero el usuario no puede leer el registro del modelo relacionado.
    """
    res = super().read(fields=fields, load=load)

    # Si fields=None, Odoo usa un set por defecto (normalmente incluye partner_invoice_id en venta)
    field_names = fields or []
    # Si fields es None, igual sanitizamos los many2one presentes en el resultado (por seguridad)
    if not field_names and res:
        field_names = list(res[0].keys())

    # Identifica campos many2one presentes
    m2o_fields = []
    for fname in field_names:
        f = self._fields.get(fname)
        if f and f.type == 'many2one':
            m2o_fields.append((fname, f.comodel_name))

    if not m2o_fields:
        return res

    for fname, comodel in m2o_fields:
        ids = {vals.get(fname) for vals in res if vals.get(fname)}
        if not ids:
            continue
        # exists() bajo reglas del usuario -> solo IDs accesibles
        accessible = set(self.env[comodel].browse(list(ids)).exists().ids)
        if accessible == ids:
            continue
        for vals in res:
            vid = vals.get(fname)
            if vid and vid not in accessible:
                # fallback específico para invoice contact
                if fname == 'partner_invoice_id' and vals.get('partner_id'):
                    vals['partner_invoice_id'] = vals['partner_id']
                else:
                    vals[fname] = False

    return res
