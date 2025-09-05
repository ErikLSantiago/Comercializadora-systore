
from odoo import api, fields, models

class StockPicking(models.Model):
    _inherit = "stock.picking"

    serial_captured_count = fields.Integer(
        compute="_compute_serial_flags",
        string="Seriales capturados",
        store=False,
    )
    serial_expected_qty = fields.Integer(
        compute="_compute_serial_flags",
        string="Demanda (serializada)",
        store=False,
    )
    serial_complete = fields.Boolean(compute="_compute_serial_flags", store=False)
    serial_partial = fields.Boolean(compute="_compute_serial_flags", store=False)
    serial_none = fields.Boolean(compute="_compute_serial_flags", store=False)

    @api.depends("move_ids_without_package.product_id", "move_ids_without_package.product_uom_qty", "state")
    def _compute_serial_flags(self):
        Serial = self.env["stock.move.line.serial"]
        for picking in self:
            captured = Serial.search_count([("picking_id", "=", picking.id)])
            expected = 0
            for m in picking.move_ids_without_package:
                if m.product_id and m.product_id.tracking == "serial":
                    expected += int(round(m.product_uom_qty or 0))
            picking.serial_captured_count = captured
            picking.serial_expected_qty = expected
            picking.serial_complete = (expected > 0 and captured >= expected)
            picking.serial_partial = (captured > 0 and captured < expected)
            picking.serial_none = (captured == 0)
