# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

def _tokenize_serials(text):
    if not text:
        return []
    raw = text.replace("\r", "\n")
    for s in [",", ";", "\t"]:
        raw = raw.replace(s, "\n")
    tokens = [t.strip() for t in raw.split("\n")]
    out = []
    for t in tokens:
        for part in t.split(" "):
            part = part.strip()
            if part:
                out.append(part)
    return out

class SerialCaptureWizard(models.TransientModel):
    _name = "serial.capture.wizard"
    _description = "Captura opcional de números de serie en operación"

    picking_id = fields.Many2one("stock.picking", string="Operación", required=True, ondelete="cascade")
    mode = fields.Selection([
        ("auto", "Distribuir automáticamente en todas las líneas"),
        ("product", "Aplicar a un producto específico"),
    ], default="auto", required=True, string="Modo de asignación")
    product_id = fields.Many2one("product.product", string="Producto (si aplica)", domain="[('id', 'in', available_product_ids)]")
    available_product_ids = fields.Many2many("product.product", compute="_compute_available_products")
    paste_text = fields.Text(string="Pegar números de serie (uno por línea o separados por comas)")
    allow_mismatch = fields.Boolean(string="Permitir diferencia en cantidades", default=False)
    clear_existing = fields.Boolean(string="Limpiar seriales existentes en el alcance", default=True)
    only_unassigned = fields.Boolean(string="Solo líneas con cantidad a procesar", default=True)

    total_needed = fields.Integer(string="Piezas objetivo", compute="_compute_totals")
    total_entered = fields.Integer(string="Seriales pegados", compute="_compute_totals")

    def _compute_available_products(self):
        for w in self:
            w.available_product_ids = [(6, 0, w.picking_id.move_line_ids.product_id.ids)]

    def _compute_totals(self):
        for w in self:
            lines = w._target_move_lines()
            w.total_needed = sum(self._line_qty_target(l) for l in lines)
            w.total_entered = len(_tokenize_serials(w.paste_text))

    @api.model
    def _line_qty_target(self, ml):
        qty = ml.qty_done or 0.0
        if not qty:
            qty = getattr(ml, "reserved_uom_qty", 0.0) or 0.0
        if not qty and ml.move_id:
            qty = ml.move_id.product_uom_qty or 0.0
        return int(round(qty))

    def _target_move_lines(self):
        self.ensure_one()
        mls = self.picking_id.move_line_ids
        if self.only_unassigned:
            mls = mls.filtered(lambda ml: self._line_qty_target(ml) > len(ml.serial_captured_ids))
        if self.mode == "product" and self.product_id:
            mls = mls.filtered(lambda ml: ml.product_id.id == self.product_id.id)
        return mls.sorted(lambda ml: (ml.sequence, ml.id))

    def action_apply(self):
        self.ensure_one()
        serials = _tokenize_serials(self.paste_text)
        lines = self._target_move_lines()

        needed = sum(self._line_qty_target(ml) for ml in lines)
        if not self.allow_mismatch:
            if len(serials) != needed:
                raise UserError(_("La cantidad de números de serie (%s) no coincide con las piezas objetivo (%s).") % (len(serials), needed))
            if not serials:
                raise UserError(_("No se proporcionaron números de serie."))

        if self.clear_existing:
            self.env["stock.move.line.serial"].search([("move_line_id", "in", lines.ids)]).unlink()

        seen, dups = set(), set()
        for s in serials:
            if s in seen:
                dups.add(s)
            seen.add(s)
        if dups:
            raise UserError(_("Existen números de serie duplicados en la entrada: %s") % (", ".join(sorted(dups))))

        to_create, s_idx = [], 0
        for ml in lines:
            qty_target = self._line_qty_target(ml)
            assign_n = min(qty_target, len(serials) - s_idx) if self.allow_mismatch else qty_target
            for _ in range(assign_n):
                to_create.append({"name": serials[s_idx], "move_line_id": ml.id})
                s_idx += 1
                if s_idx >= len(serials):
                    break
            if s_idx >= len(serials):
                break

        if not to_create and serials:
            raise UserError(_("No se pudo asignar ningún número de serie. Verifique el alcance y cantidades."))

        self.env["stock.move.line.serial"].create(to_create)
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "view_mode": "form",
            "res_id": self.picking_id.id,
            "target": "current",
        }
