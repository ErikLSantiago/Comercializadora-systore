from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    x_sale_lot_id = fields.Many2one(
        "stock.lot",
        string="Serial/Lote vendido",
        help="Serial/Lote elegido para trazabilidad comercial (precio por peso).",
        copy=False,
        readonly=True,
    )

    x_reserved_serial_count = fields.Integer(
        string="Seriales reservados",
        compute="_compute_x_reserved_serial_count",
        help="Cantidad de seriales/lotes ya reservados para esta línea (según movimientos de stock).",
    )

    @api.depends("move_ids.move_line_ids.lot_id")
    def _compute_x_reserved_serial_count(self):
        for line in self:
            lots = line.move_ids.move_line_ids.mapped("lot_id")
            line.x_reserved_serial_count = len(lots)
