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

    def action_open_serial_lines_list(self):
        self.ensure_one()
        action = self.env.ref('adicional_serial_number.action_move_lines_by_picking_adicional_sn').read()[0]
        action['domain'] = [('picking_id', '=', self.id)]
        action['context'] = {'default_picking_id': self.id}
        return action

    def action_open_serial_history(self):
        self.ensure_one()
        action = self.env.ref('adicional_serial_number.action_serial_history_by_picking').read()[0]
        action['domain'] = [('picking_id', '=', self.id)]
        action['context'] = {'default_picking_id': self.id}
        return action
