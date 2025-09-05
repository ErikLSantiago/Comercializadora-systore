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

    partner_id = fields.Many2one(related="picking_id.partner_id", comodel_name="res.partner", string="Cliente/Proveedor", store=True, index=True)
    origin = fields.Char(related="picking_id.origin", string="Origen", store=True, index=True)
    lot_id = fields.Many2one(related="move_line_id.lot_id", comodel_name="stock.lot", string="Lote/Serie (nativo)", store=True, index=True)
    carrier_tracking_ref = fields.Char(string="Guía/Tracking", compute="_compute_carrier_tracking_ref", store=False)

    _sql_constraints = [
        ("uniq_serial_per_picking", "unique(name, picking_id)", "Este número de serie ya existe en esta operación."),
    ]

    def _compute_carrier_tracking_ref(self):
        for rec in self:
            val = False
            picking = rec.picking_id
            try:
                if picking and 'carrier_tracking_ref' in picking._fields:
                    val = picking.carrier_tracking_ref or False
            except Exception:
                val = False
            rec.carrier_tracking_ref = val

    # Bloquear edición si picking validado/cancelado
    def _check_editable_state(self):
        for rec in self:
            if rec.picking_id and rec.picking_id.state in ('done', 'cancel'):
                from odoo.exceptions import UserError
                raise UserError(_("No puedes modificar seriales porque la operación ya está %s.") % (dict(self.env['stock.picking']._fields['state'].selection).get(rec.picking_id.state, rec.picking_id.state)))
        return True

    def write(self, vals):
        self._check_editable_state()
        return super().write(vals)

    def unlink(self):
        self._check_editable_state()
        return super().unlink()

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
