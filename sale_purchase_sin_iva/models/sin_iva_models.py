
# -*- coding: utf-8 -*-
from odoo import api, fields, models

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    sin_iva_price_unit = fields.Monetary(
        string="Sin IVA",
        compute="_compute_sin_iva_line",
        currency_field="currency_id",
        help="Precio unitario sin IVA (price_unit / 1.16).",
        store=False,
    )
    sin_iva_price_subtotal = fields.Monetary(
        string="Total sin IVA",
        compute="_compute_sin_iva_line",
        currency_field="currency_id",
        help="Total sin IVA por línea (Sin IVA * Cantidad).",
        store=False,
    )

    @api.depends("price_unit", "product_uom_qty", "currency_id")
    def _compute_sin_iva_line(self):
        for line in self:
            price_wo_iva = (line.price_unit or 0.0) / 1.16
            subtotal_wo_iva = price_wo_iva * (line.product_uom_qty or 0.0)
            line.sin_iva_price_unit = line.currency_id.round(price_wo_iva)
            line.sin_iva_price_subtotal = line.currency_id.round(subtotal_wo_iva)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    amount_subtotal_sin_iva = fields.Monetary(
        string="Subtotal (Sin IVA)",
        compute="_compute_totals_sin_iva",
        currency_field="currency_id",
        store=False,
    )
    amount_iva_16 = fields.Monetary(
        string="IVA (16%)",
        compute="_compute_totals_sin_iva",
        currency_field="currency_id",
        store=False,
    )
    amount_total_sin_iva = fields.Monetary(
        string="Total",
        compute="_compute_totals_sin_iva",
        currency_field="currency_id",
        store=False,
        help="Total de presentación = Subtotal (Sin IVA) + IVA (16%)."
    )

    @api.depends("order_line.sin_iva_price_subtotal", "currency_id")
    def _compute_totals_sin_iva(self):
        for order in self:
            subtotal = sum(order.order_line.mapped("sin_iva_price_subtotal"))
            iva = order.currency_id.round(subtotal * 0.16)
            total = order.currency_id.round(subtotal + iva)
            order.amount_subtotal_sin_iva = order.currency_id.round(subtotal)
            order.amount_iva_16 = iva
            order.amount_total_sin_iva = total


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    sin_iva_price_unit = fields.Monetary(
        string="Sin IVA",
        compute="_compute_sin_iva_line",
        currency_field="currency_id",
        help="Precio unitario sin IVA (price_unit / 1.16).",
        store=False,
    )
    sin_iva_price_subtotal = fields.Monetary(
        string="Total sin IVA",
        compute="_compute_sin_iva_line",
        currency_field="currency_id",
        help="Total sin IVA por línea (Sin IVA * Cantidad).",
        store=False,
    )

    @api.depends("price_unit", "product_qty", "currency_id")
    def _compute_sin_iva_line(self):
        for line in self:
            price_wo_iva = (line.price_unit or 0.0) / 1.16
            subtotal_wo_iva = price_wo_iva * (line.product_qty or 0.0)
            line.sin_iva_price_unit = line.currency_id.round(price_wo_iva)
            line.sin_iva_price_subtotal = line.currency_id.round(subtotal_wo_iva)


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    amount_subtotal_sin_iva = fields.Monetary(
        string="Subtotal (Sin IVA)",
        compute="_compute_totals_sin_iva",
        currency_field="currency_id",
        store=False,
    )
    amount_iva_16 = fields.Monetary(
        string="IVA (16%)",
        compute="_compute_totals_sin_iva",
        currency_field="currency_id",
        store=False,
    )
    amount_total_sin_iva = fields.Monetary(
        string="Total",
        compute="_compute_totals_sin_iva",
        currency_field="currency_id",
        store=False,
        help="Total de presentación = Subtotal (Sin IVA) + IVA (16%)."
    )

    @api.depends("order_line.sin_iva_price_subtotal", "currency_id")
    def _compute_totals_sin_iva(self):
        for order in self:
            subtotal = sum(order.order_line.mapped("sin_iva_price_subtotal"))
            iva = order.currency_id.round(subtotal * 0.16)
            total = order.currency_id.round(subtotal + iva)
            order.amount_subtotal_sin_iva = order.currency_id.round(subtotal)
            order.amount_iva_16 = iva
            order.amount_total_sin_iva = total
