# -*- coding: utf-8 -*-
from odoo import api, fields, models

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    currency_id = fields.Many2one(related='order_id.currency_id', string='Currency', readonly=True, store=False)
    sin_iva_price_unit = fields.Monetary(
        string='Sin IVA',
        currency_field='currency_id',
        compute='_compute_sin_iva_fields',
        store=False,
        readonly=True,
    )
    sin_iva_price_subtotal = fields.Monetary(
        string='Total sin IVA',
        currency_field='currency_id',
        compute='_compute_sin_iva_fields',
        store=False,
        readonly=True,
    )

    @api.depends('price_unit', 'product_qty')
    def _compute_sin_iva_fields(self):
        for line in self:
            unit = (line.price_unit or 0.0) / 1.16 if line.price_unit else 0.0
            subtotal = unit * (line.product_qty or 0.0)
            line.sin_iva_price_unit = unit
            line.sin_iva_price_subtotal = subtotal


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    amount_subtotal_sin_iva = fields.Monetary(
        string='Subtotal sin IVA', currency_field='currency_id',
        compute='_compute_amounts_sin_iva', store=False, readonly=True)
    amount_tax_sin_iva = fields.Monetary(
        string='IVA (16%)', currency_field='currency_id',
        compute='_compute_amounts_sin_iva', store=False, readonly=True)
    amount_total_sin_iva = fields.Monetary(
        string='Total sin IVA', currency_field='currency_id',
        compute='_compute_amounts_sin_iva', store=False, readonly=True)

    @api.depends('order_line.sin_iva_price_subtotal')
    def _compute_amounts_sin_iva(self):
        for order in self:
            subtotal = sum(order.order_line.mapped('sin_iva_price_subtotal'))
            tax = subtotal * 0.16
            order.amount_subtotal_sin_iva = subtotal
            order.amount_tax_sin_iva = tax
            order.amount_total_sin_iva = subtotal + tax