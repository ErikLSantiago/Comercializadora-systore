
# -*- coding: utf-8 -*-
from odoo import api, fields, models

RATE = 1.16

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    sin_iva_price_unit = fields.Monetary(string="Sin IVA (unit.)", currency_field="currency_id",
                                         compute="_compute_sin_iva_prices", store=True)
    sin_iva_price_subtotal = fields.Monetary(string="Total sin IVA", currency_field="currency_id",
                                             compute="_compute_sin_iva_prices", store=True)

    @api.depends('price_unit', 'product_uom_qty')
    def _compute_sin_iva_prices(self):
        for line in self:
            unit = (line.price_unit or 0.0) / RATE
            subtotal = unit * (line.product_uom_qty or 0.0)
            if line.currency_id:
                unit = line.currency_id.round(unit)
                subtotal = line.currency_id.round(subtotal)
            line.sin_iva_price_unit = unit
            line.sin_iva_price_subtotal = subtotal


class SaleOrder(models.Model):
    _inherit = "sale.order"

    amount_untaxed_sin_iva = fields.Monetary(string="Subtotal (Sin IVA)",
                                             compute="_compute_amounts_sin_iva", store=True)
    amount_tax_sin_iva = fields.Monetary(string="IVA (16%)",
                                         compute="_compute_amounts_sin_iva", store=True)
    amount_total_sin_iva = fields.Monetary(string="Total (Sin IVA + IVA)",
                                           compute="_compute_amounts_sin_iva", store=True)

    @api.depends('order_line.sin_iva_price_subtotal')
    def _compute_amounts_sin_iva(self):
        for order in self:
            subtotal = sum(order.order_line.mapped('sin_iva_price_subtotal'))
            tax = order.currency_id.round(subtotal * 0.16) if order.currency_id else subtotal * 0.16
            total = subtotal + tax
            order.update({
                'amount_untaxed_sin_iva': subtotal,
                'amount_tax_sin_iva': tax,
                'amount_total_sin_iva': total,
            })
