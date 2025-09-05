# -*- coding: utf-8 -*-
from odoo import models, _

class StockPicking(models.Model):
    _inherit = "stock.picking"

    def action_open_serial_capture_wizard(self):
        self.ensure_one()
        return {
            "name": _("Capturar números de serie (adicional)"),
            "type": "ir.actions.act_window",
            "res_model": "serial.capture.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_picking_id": self.id},
        }
