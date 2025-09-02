# -*- coding: utf-8 -*-
from odoo import api, fields, models

IVA_FACTOR = 1.16

class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    sin_iva_price_unit = fields.Monetary(
        string="Sin IVA",
        compute="_compute_sin_iva_fields",
        currency_field="currency_id",
        store=True,
    )
    sin_iva_price_subtotal = fields.Monetary(
        string="Total sin IVA",
        compute="_compute_sin_iva_fields",
        currency_field="currency_id",
        store=True,
    )

    @api.depends("price_unit", "product_qty")
    def _compute_sin_iva_fields(self):
        for line in self:
            unit = (line.price_unit or 0.0) / IVA_FACTOR
            subtotal = unit * (line.product_qty or 0.0)
            line.sin_iva_price_unit = unit
            line.sin_iva_price_subtotal = subtotal

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    amount_untaxed_sin_iva = fields.Monetary(
        string="Subtotal (sin IVA)",
        currency_field="currency_id",
        compute="_compute_amounts_sin_iva",
        store=True,
    )
    amount_iva_sin_iva = fields.Monetary(
        string="IVA (16%)",
        currency_field="currency_id",
        compute="_compute_amounts_sin_iva",
        store=True,
    )
    amount_total_sin_iva = fields.Monetary(
        string="Total (sin IVA)",
        currency_field="currency_id",
        compute="_compute_amounts_sin_iva",
        store=True,
    )

    @api.depends("order_line.sin_iva_price_subtotal")
    def _compute_amounts_sin_iva(self):
        for order in self:
            subtotal = sum(order.order_line.mapped("sin_iva_price_subtotal"))
            iva = subtotal * 0.16
            total = subtotal + iva
            order.amount_untaxed_sin_iva = subtotal
            order.amount_iva_sin_iva = iva
            order.amount_total_sin_iva = total