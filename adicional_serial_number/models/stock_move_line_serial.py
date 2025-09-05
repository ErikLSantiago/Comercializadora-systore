# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class StockMoveLineSerial(models.Model):
    _name = "stock.move.line.serial"
    _description = "Serial capturado (adicional, no nativo)"
    _order = "create_date desc, id desc"

    name = fields.Char(string="Número de serie", required=True, index=True)
    move_line_id = fields.Many2one("stock.move.line", string="Línea de movimiento", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one(related="move_line_id.product_id", string="Producto", store=True, index=True)
    picking_id = fields.Many2one(related="move_line_id.picking_id", string="Operación", store=True, index=True)
    date = fields.Datetime(related="move_line_id.date", string="Fecha de operación", store=True)
    company_id = fields.Many2one(related="move_line_id.company_id", string="Compañía", store=True, index=True)

    _sql_constraints = [
        ("uniq_serial_per_picking", "unique(name, picking_id)", "Este número de serie ya existe en esta operación."),
    ]

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    serial_captured_ids = fields.One2many("stock.move.line.serial", "move_line_id", string="Números de serie (adicionales)")
    serial_captured_count = fields.Integer(compute="_compute_serial_captured_count", string="# Seriales (adicionales)", store=False)

    def _compute_serial_captured_count(self):
        for ml in self:
            ml.serial_captured_count = len(ml.serial_captured_ids)

class StockPicking(models.Model):
    _inherit = "stock.picking"

    serial_captured_count = fields.Integer(compute="_compute_serial_captured_count", string="# Seriales (adicionales)", store=False)

    def _compute_serial_captured_count(self):
        for picking in self:
            picking.serial_captured_count = self.env["stock.move.line.serial"].search_count([("picking_id", "=", picking.id)])
