# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AdicionalSNProductLine(models.TransientModel):
    _name = "adicional.sn.product.line"
    _description = "Resumen por producto (adicional SN)"
    _order = "product_id"

    session_token = fields.Char(index=True)
    picking_id = fields.Many2one("stock.picking", string="Operación", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one("product.product", string="Producto", required=True, index=True)
    demand_total = fields.Float(string="Demanda total", digits="Product Unit of Measure")
    reserved_total = fields.Float(string="Reservado total", digits="Product Unit of Measure")
    captured_label = fields.Char(string="Estado")

    def action_open_serial_product_wizard(self):
        self.ensure_one()
        return {
            "name": _("Capturar números de serie (producto)"),
            "type": "ir.actions.act_window",
            "res_model": "serial.capture.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_picking_id": self.picking_id.id,
                "default_mode": "product",
                "default_product_id": self.product_id.id,
                "default_only_unassigned": True,
                "default_move_line_id": False,
            },
        }
