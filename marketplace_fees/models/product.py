# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ProductTemplate(models.Model):
    _inherit = "product.template"

    marketplace_fee_config_ids = fields.One2many(
        "product.marketplace.fee.config",
        "product_tmpl_id",
        string="Comisiones por Marketplace",
        help="Configura la comisión (%) y el costo de envío por canal para este producto."
    )


class ProductMarketplaceFeeConfig(models.Model):
    _name = "product.marketplace.fee.config"
    _description = "Configuración de Comisiones por Producto y Marketplace"
    _order = "id desc"

    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Producto",
        required=True,
        ondelete="cascade",
    )

    producteca_channel_id = fields.Many2one(
        "producteca.channel",
        string="Marketplace",
        help="Selecciona el canal de Producteca. Se aplicará tanto si la orden trae el binding como el canal base."
    )

    channel_ref = fields.Reference(
        selection="_get_channel_models",
        string="Marketplace (legacy)",
        required=False,
        help="Compatibilidad: configuración previa que usaba Reference a binding/canal."
    )

    commission_percent = fields.Float(
        string="Comisión (%)",
        digits=(16, 2),
        help="Porcentaje sobre el subtotal sin impuestos para calcular la comisión."
    )
    shipping_cost = fields.Monetary(
        string="Costo envío por unidad",
        help="Costo fijo de envío por unidad para este marketplace."
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        default=lambda self: self.env.company.currency_id.id,
        required=True,
        help="Moneda utilizada para el costo de envío."
    )

    commission_product_id = fields.Many2one(
        "product.product",
        string="Producto servicio (Comisión)",
        domain=[("type", "=", "service")],
        required=True,
        help="Producto de servicio utilizado para la línea de comisión."
    )
    shipping_product_id = fields.Many2one(
        "product.product",
        string="Producto servicio (Envío)",
        domain=[("type", "=", "service")],
        required=True,
        help="Producto de servicio utilizado para la línea de envío."
    )

    commission_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de gasto (Comisión)",
        help="Si se define, la línea/partida contable de comisión usará esta cuenta de gasto."
    )
    shipping_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de gasto (Envío)",
        help="Si se define, la línea/partida contable de envío usará esta cuenta de gasto."
    )

    revenue_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de ingresos (Venta)",
        domain="[('internal_group', '=', 'income')]",
        help="Si se define, las líneas de venta del producto para este marketplace usarán esta cuenta de ingresos en lugar de la del producto/categoría. Se respeta la Posición Fiscal para mapear la cuenta."
    )

    @api.model
    def _get_channel_models(self):
        results = []
        imf = self.env["ir.model.fields"].sudo().search([
            ("model", "=", "sale.order"),
            ("name", "=", "channel_binding_id"),
        ], limit=1)
        if imf and imf.relation:
            im = self.env["ir.model"].sudo().search([("model", "=", imf.relation)], limit=1)
            label = im.name or imf.relation
            results.append((imf.relation, label))
            if imf.relation.endswith(".channel.binding"):
                base_model = imf.relation.replace(".channel.binding", ".channel")
                im_base = self.env["ir.model"].sudo().search([("model", "=", base_model)], limit=1)
                if im_base:
                    results.append((base_model, im_base.name or base_model))
        else:
            imf2 = self.env["ir.model.fields"].sudo().search([
                ("model", "=", "sale.order"),
                ("name", "=", "producteca_channel_binding"),
            ], limit=1)
            if imf2 and imf2.relation:
                im = self.env["ir.model"].sudo().search([("model", "=", imf2.relation)], limit=1)
                label = im.name or imf2.relation
                results.append((imf2.relation, label))
                if imf2.relation.endswith(".channel.binding"):
                    base_model = imf2.relation.replace(".channel.binding", ".channel")
                    im_base = self.env["ir.model"].sudo().search([("model", "=", base_model)], limit=1)
                    if im_base:
                        results.append((base_model, im_base.name or base_model))
        if not results and "sale.channel" in self.env:
            im = self.env["ir.model"].sudo().search([("model", "=", "sale.channel")], limit=1)
            results.append(("sale.channel", im.name or "sale.channel"))
        return results

    def name_get(self):
        res = []
        for rec in self:
            if rec.producteca_channel_id:
                name = rec.producteca_channel_id.display_name
            elif rec.channel_ref:
                name = rec.channel_ref.display_name
            else:
                name = _("(Sin marketplace)")
            res.append((rec.id, name))
        return res

    @api.constrains("product_tmpl_id", "producteca_channel_id", "channel_ref")
    def _check_unique_product_channel(self):
        for rec in self:
            domain = [("id", "!=", rec.id), ("product_tmpl_id", "=", rec.product_tmpl_id.id)]
            if rec.producteca_channel_id:
                dup = self.search_count(domain + [("producteca_channel_id", "=", rec.producteca_channel_id.id)])
                if dup:
                    raise models.ValidationError(_("Ya existe una configuración para este producto y marketplace."))
            elif rec.channel_ref:
                dup = self.search_count(domain + [("channel_ref", "=", "%s,%s" % (rec.channel_ref._name, rec.channel_ref.id))])
                if dup:
                    raise models.ValidationError(_("Ya existe una configuración para este producto y marketplace."))
