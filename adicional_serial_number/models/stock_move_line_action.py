# -*- coding: utf-8 -*-
from odoo import models, fields, _

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    reserved_qty_info = fields.Float(string="Cantidad Reservada", compute="_compute_reserved_qty_info", digits="Product Unit of Measure")
    demand_qty_info = fields.Float(string="Demanda", compute="_compute_demand_qty_info", digits="Product Unit of Measure")
    reserved_by_lot_info = fields.Char(string="Reservado por lote", compute="_compute_reserved_by_lot_info")

    def _compute_reserved_qty_info(self):
        for ml in self:
            qty = getattr(ml, 'reserved_uom_qty', 0.0) or getattr(ml, 'reserved_quantity', 0.0) or 0.0
            ml.reserved_qty_info = qty

    def _compute_demand_qty_info(self):
        for ml in self:
            qty = 0.0
            if ml.move_id and 'product_uom_qty' in ml.move_id._fields:
                qty = ml.move_id.product_uom_qty or 0.0
            ml.demand_qty_info = qty

    def _compute_reserved_by_lot_info(self):
        for ml in self:
            # Mejor detector de cantidad reservada en v17/v18:
            # 1) 'quantity' (cantidad a procesar en la línea)
            # 2) 'reserved_uom_qty' o 'reserved_quantity' (dependiendo de la base)
            # 3) 'qty_done' como fallback visual
            qty = 0.0
            if 'quantity' in ml._fields:
                qty = ml.quantity or 0.0
            if not qty:
                qty = getattr(ml, 'reserved_uom_qty', 0.0) or getattr(ml, 'reserved_quantity', 0.0) or 0.0
            if not qty:
                qty = getattr(ml, 'qty_done', 0.0) or 0.0

            lot_name = False
            if 'lot_id' in ml._fields and ml.lot_id:
                lot_name = ml.lot_id.display_name or ml.lot_id.name
            elif 'lot_name' in ml._fields and ml.lot_name:
                lot_name = ml.lot_name
            ml.reserved_by_lot_info = f"{lot_name}: {qty:g}" if lot_name else f"{qty:g}"

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
