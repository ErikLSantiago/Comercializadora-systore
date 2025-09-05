
from odoo import api, fields, models, _


class StockPicking(models.Model):
    _inherit = "stock.picking"

    serial_captured_count = fields.Integer(
        compute="_compute_serial_totals",
        string="Seriales capturados",
        store=False,
    )
    serial_demand_total = fields.Float(
        compute="_compute_serial_totals",
        string="Demanda total (producto)",
        store=False,
    )

    @api.depends("move_ids_without_package.product_uom_qty", "move_ids_without_package.product_id")
    def _compute_serial_totals(self):
        Serial = self.env["stock.move.line.serial"]
        for picking in self:
            picking.serial_captured_count = Serial.search_count([("picking_id", "=", picking.id)])
            # suma demanda por producto (no por lotes)
            demand = 0.0
            for m in picking.move_ids_without_package:
                demand += m.product_uom_qty
            picking.serial_demand_total = demand
