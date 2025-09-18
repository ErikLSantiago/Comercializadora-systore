
# -*- coding: utf-8 -*-
from odoo import models, fields, api

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    usd_mx = fields.Float(string="Tipo de cambio USD→MX", digits=(16, 6), default=1.0)

    subtotal_total_usd = fields.Float(
        string="Subtotal Total USD", compute="_compute_subtotals", store=True
    )
    subtotal_shipping_mx = fields.Float(
        string="Envío Total MX", compute="_compute_subtotals", store=True
    )
    subtotal_import_mx = fields.Float(
        string="Import. total MX", compute="_compute_subtotals", store=True
    )
    subtotal_lines_usd_mx = fields.Float(
        string="Líneas Total MX (USD→MX)",
        compute="_compute_subtotals", store=True,
        help="Conversión a MX del subtotal USD de líneas (Total USD × tipo de cambio).",
    )
    subtotal_grand_total_mx = fields.Float(
        string="Total MX",
        compute="_compute_subtotals", store=True,
        help="Suma de Importación MX + Envío MX + Líneas MX (USD→MX).",
    )

    @api.depends('order_line.total_usd',
                 'order_line.shipping_total_mx',
                 'order_line.import_total_mx',
                 'usd_mx')
    def _compute_subtotals(self):
        for order in self:
            total_usd = sum(order.order_line.mapped('total_usd'))
            envio_mx = sum(order.order_line.mapped('shipping_total_mx'))
            import_mx = sum(order.order_line.mapped('import_total_mx'))
            lines_mx = total_usd * (order.usd_mx or 0.0)
            order.subtotal_total_usd = total_usd
            order.subtotal_shipping_mx = envio_mx
            order.subtotal_import_mx = import_mx
            order.subtotal_lines_usd_mx = lines_mx
            order.subtotal_grand_total_mx = import_mx + envio_mx + lines_mx


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    price_unit_usd = fields.Float(string="Unitario USD")
    shipping_cost_usd = fields.Float(string="Envío (USD)")
    import_cost_mx = fields.Float(string="Import. (MX)")

    total_usd = fields.Float(string="Total USD", compute="_compute_totals", store=True)
    total_usd_mx = fields.Float(string="Total USD → MX", compute="_compute_totals", store=True)
    shipping_total_mx = fields.Float(string="Envío Total MX", compute="_compute_totals", store=True)
    import_total_mx = fields.Float(string="Import. total MX", compute="_compute_totals", store=True)

    @api.depends('product_qty', 'price_unit_usd', 'shipping_cost_usd', 'import_cost_mx', 'order_id.usd_mx')
    def _compute_totals(self):
        for line in self:
            qty = line.product_qty or 0.0
            tc = line.order_id.usd_mx or 0.0
            line.total_usd = qty * (line.price_unit_usd or 0.0)
            line.total_usd_mx = line.total_usd * tc
            line.shipping_total_mx = qty * (line.shipping_cost_usd or 0.0) * tc
            line.import_total_mx = qty * (line.import_cost_mx or 0.0)
