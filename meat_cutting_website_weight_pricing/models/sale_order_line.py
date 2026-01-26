from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    x_web_reserved_lot_ids = fields.Many2many(
        comodel_name="stock.lot",
        relation="sale_order_line_mc_web_lot_rel",
        column1="sale_line_id",
        column2="lot_id",
        string="Lotes reservados (web)",
        help="Lotes/seriales seleccionados y reservados al llegar a checkout (paso de pago).",
        readonly=True,
        copy=False,
    )

    x_web_reserved_lot_display = fields.Char(
        string="Lotes reservados (web)",
        help="Se llena automáticamente cuando el cliente llega a checkout (paso de pago).",
    )
