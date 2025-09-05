# -*- coding: utf-8 -*-
from odoo import models, fields, _

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    reserved_qty_info = fields.Float(string="Cantidad Reservada", compute="_compute_reserved_qty_info", digits="Product Unit of Measure")

    def _compute_reserved_qty_info(self):
        for ml in self:
            qty = getattr(ml, 'reserved_uom_qty', 0.0) or getattr(ml, 'reserved_quantity', 0.0) or 0.0
            ml.reserved_qty_info = qty

    def action_open_serial_line_wizard(self):
        self.ensure_one()
        return {
            "name": _("Capturar números de serie (línea)"),
            "type": "ir.actions.act_window",
            "res_model": "serial.capture.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_picking_id": self.picking_id.id,
                "default_move_line_id": self.id,
                "default_mode": "auto",
                "default_only_unassigned": False,
            },
        }
