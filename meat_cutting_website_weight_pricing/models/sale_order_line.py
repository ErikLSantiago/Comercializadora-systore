from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    x_web_reserved_lot_display = fields.Char(
        string="Lotes reservados (web)",
        help="Se llena automáticamente cuando el cliente llega a checkout (paso de pago) para explicar el precio exacto.",
        readonly=True,
        copy=False,
    )
