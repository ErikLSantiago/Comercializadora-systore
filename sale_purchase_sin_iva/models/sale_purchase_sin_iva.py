# -*- coding: utf-8 -*-
from odoo import api, fields, models

IVA_FACTOR = 1.16

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    sin_iva_price_unit = fields.Monetary(
        string='Sin IVA (Unit)',
        currency_field='currency_id',
        compute='_compute_sin_iva_fields',
        store=False,
        help='price_unit / 1.16'
    )
    sin_iva_price_subtotal = fields.Monetary(
        string='Total sin IVA',
        currency_field='currency_id',
        compute='_compute_sin_iva_fields',
        store=False
    )

    @api.depends('price_unit', 'product_uom_qty')
    def _compute_sin_iva_fields(self):
        for line in self:
            unit = (line.price_unit or 0.0) / IVA_FACTOR
            subtotal = unit * (line.product_uom_qty or 0.0)
            line.sin_iva_price_unit = unit
            line.sin_iva_price_subtotal = subtotal


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    amount_subtotal_sin_iva = fields.Monetary(
        string='Subtotal (Sin IVA)',
        currency_field='currency_id',
        compute='_compute_amounts_sin_iva',
        store=False
    )
    amount_tax_sin_iva = fields.Monetary(
        string='IVA (16%)',
        currency_field='currency_id',
        compute='_compute_amounts_sin_iva',
        store=False
    )
    amount_total_sin_iva = fields.Monetary(
        string='Total (Sin IVA)',
        currency_field='currency_id',
        compute='_compute_amounts_sin_iva',
        store=False
    )

    def _compute_amounts_sin_iva(self):
        for order in self:
            subtotal = sum(order.order_line.mapped('sin_iva_price_subtotal'))
            tax = subtotal * 0.16
            total = subtotal + tax
            order.amount_subtotal_sin_iva = subtotal
            order.amount_tax_sin_iva = tax
            order.amount_total_sin_iva = total


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    sin_iva_price_unit = fields.Monetary(
        string='Sin IVA (Unit)',
        currency_field='currency_id',
        compute='_compute_sin_iva_fields',
        store=False,
        help='price_unit / 1.16'
    )
    sin_iva_price_subtotal = fields.Monetary(
        string='Total sin IVA',
        currency_field='currency_id',
        compute='_compute_sin_iva_fields',
        store=False
    )

    @api.depends('price_unit', 'product_qty')
    def _compute_sin_iva_fields(self):
        for line in self:
            unit = (line.price_unit or 0.0) / IVA_FACTOR
            subtotal = unit * (line.product_qty or 0.0)
            line.sin_iva_price_unit = unit
            line.sin_iva_price_subtotal = subtotal


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    amount_subtotal_sin_iva = fields.Monetary(
        string='Subtotal (Sin IVA)',
        currency_field='currency_id',
        compute='_compute_amounts_sin_iva',
        store=False
    )
    amount_tax_sin_iva = fields.Monetary(
        string='IVA (16%)',
        currency_field='currency_id',
        compute='_compute_amounts_sin_iva',
        store=False
    )
    amount_total_sin_iva = fields.Monetary(
        string='Total (Sin IVA)',
        currency_field='currency_id',
        compute='_compute_amounts_sin_iva',
        store=False
    )

    def _compute_amounts_sin_iva(self):
        for order in self:
            subtotal = sum(order.order_line.mapped('sin_iva_price_subtotal'))
            tax = subtotal * 0.16
            total = subtotal + tax
            order.amount_subtotal_sin_iva = subtotal
            order.amount_tax_sin_iva = tax
            order.amount_total_sin_iva = total
