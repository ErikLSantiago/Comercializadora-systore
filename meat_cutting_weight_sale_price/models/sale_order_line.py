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

    x_reserved_weight_kg = fields.Float(
        string="Peso reservado (kg)",
        compute="_compute_x_reserved_weight_kg",
        digits=(16, 3),
        help=(
            "Suma del peso (kg) de los lotes/números..."
        ),
    )

    @api.depends('move_ids.move_line_ids.lot_id', 'move_ids.move_line_ids.lot_id.x_weight_kg')
    def _compute_x_reserved_weight_kg(self):
        for line in self:
            lots = line.move_ids.move_line_ids.mapped('lot_id')
            # Evitar duplicados
            lots = lots.filtered(lambda l: l)
            line.x_reserved_weight_kg = sum(lots.mapped('x_weight_kg') or [])

    @api.depends("move_ids.move_line_ids.lot_id")
    def _compute_x_reserved_serial_count(self):
        for line in self:
            lots = line.move_ids.move_line_ids.mapped("lot_id")
            line.x_reserved_serial_count = len(lots)
