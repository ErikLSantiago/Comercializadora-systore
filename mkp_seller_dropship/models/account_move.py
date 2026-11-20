# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    mkp_parent_order_ref = fields.Char(
        string="Orden padre",
        copy=False,
        index=True,
        readonly=True,
    )
    mkp_parent_sale_order_id = fields.Many2one(
        "sale.order",
        string="Orden padre anterior",
        copy=False,
        readonly=True,
        help="Campo técnico conservado únicamente para migrar datos de la versión anterior.",
    )

    def init(self):
        super().init()
        self.env.cr.execute(
            """
            UPDATE account_move AS move
               SET mkp_parent_order_ref = parent.name
              FROM sale_order AS parent
             WHERE move.mkp_parent_sale_order_id = parent.id
               AND COALESCE(move.mkp_parent_order_ref, '') = ''
            """
        )

    def _mkp_get_related_sale_orders(self):
        self.ensure_one()
        sale_orders = self.invoice_line_ids.sale_line_ids.order_id
        if not sale_orders and self.invoice_origin:
            names = [x.strip() for x in (self.invoice_origin or "").split(",") if x.strip()]
            if names:
                sale_orders = self.env["sale.order"].sudo().search([("name", "in", names)], limit=10)
        return sale_orders


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    mkp_seller_order_id = fields.Many2one(
        "sale.order",
        string="Orden seller",
        compute="_compute_mkp_seller_traceability",
        store=True,
        readonly=True,
    )
    mkp_seller_id = fields.Many2one(
        "res.partner",
        string="Seller",
        compute="_compute_mkp_seller_traceability",
        store=True,
        readonly=True,
    )

    @api.depends("sale_line_ids", "sale_line_ids.order_id")
    def _compute_mkp_seller_traceability(self):
        for line in self:
            sale_orders = line.sale_line_ids.mapped("order_id")
            seller_order = sale_orders.filtered(lambda order: bool(order._mkp_get_seller()))[:1]
            line.mkp_seller_order_id = seller_order
            line.mkp_seller_id = seller_order._mkp_get_seller() if seller_order else False
