# -*- coding: utf-8 -*-
from odoo import fields, models

class MCWebReservation(models.Model):
    _name = "mc.web.reservation"
    _description = "Meat Cutting - Website Lot Reservation"
    _order = "reserved_until asc, id asc"

    order_id = fields.Many2one("sale.order", required=True, ondelete="cascade", index=True)
    order_line_id = fields.Many2one("sale.order.line", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one("product.product", related="order_line_id.product_id", store=True, index=True, readonly=True)
    lot_id = fields.Many2one("stock.lot", string="Lote/Serie", required=True, ondelete="restrict", index=True)
    reserved_until = fields.Datetime(required=True, index=True)
    company_id = fields.Many2one("res.company", related="order_id.company_id", store=True, readonly=True, index=True)
