from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    x_sale_lot_id = fields.Many2one(
        "stock.lot",
        string="Serial/Lote vendido",
        help="Serial/Lote asignado para trazabilidad comercial (precio por peso).",
        copy=False,
        readonly=True,
    )
