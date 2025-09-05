# -*- coding: utf-8 -*-
from odoo import models, _

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

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
