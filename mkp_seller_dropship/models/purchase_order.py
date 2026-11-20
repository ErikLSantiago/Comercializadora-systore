# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    mkp_sale_order_id = fields.Many2one(
        "sale.order",
        string="Orden de venta asociada",
        copy=False,
        readonly=True,
        index=True,
    )
    mkp_seller_settlement = fields.Boolean(
        string="Compra de inventario seller",
        copy=False,
        readonly=True,
        index=True,
        help=(
            "La mercancía ya fue registrada en la ubicación interna del seller. "
            "Esta OC documenta la compra y no genera otra recepción."
        ),
    )

    def _create_picking(self):
        """Avoid duplicating inventory already received into the seller location."""
        regular_orders = self.filtered(lambda po: not po.mkp_seller_settlement)
        if regular_orders:
            return super(PurchaseOrder, regular_orders)._create_picking()
        return True
