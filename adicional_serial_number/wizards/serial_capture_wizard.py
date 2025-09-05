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
    move_line_id = fields.Many2one('stock.move.line', string='Línea específica (opcional)', ondelete='cascade')
    mode = fields.Selection([
        ("auto", "Distribuir automáticamente en todas las líneas"),
        ("product", "Aplicar a un producto específico"),
    ], default="auto", required=True, string="Modo de asignación")
    product_id = fields.Many2one("product.product", string="Producto (si aplica)", domain="[('id', 'in', available_product_ids)]")
    available_product_ids = fields.Many2many("product.product", compute="_compute_available_products")
    paste_text = fields.Text(string="Pegar números de serie (uno por línea o separados por comas)")

    allow_mismatch = fields.Boolean(string="Permitir diferencia en cantidades", default=True, help="Si está desactivado, debe coincidir el # de seriales con las piezas objetivo.")
    check_global_duplicate = fields.Boolean(string="Validar duplicado global", default=True, help="Si está activo, verifica que los seriales no existan en otras operaciones.")
    clear_existing = fields.Boolean(string="Limpiar seriales existentes en el alcance", default=True)
    only_unassigned = fields.Boolean(string="Solo líneas con cantidad a procesar", default=True)

    total_needed = fields.Integer(string="Piezas objetivo", compute="_compute_totals")
    total_entered = fields.Integer(string="Seriales pegados", compute="_compute_totals")
    entered_serials_preview = fields.Text(string="Vista previa de seriales", compute="_compute_totals")
    demand_qty_line = fields.Float(string="Demanda del producto", compute="_compute_demand_qty_line")

    def _compute_available_products(self):
        for w in self:
            w.available_product_ids = [(6, 0, w.picking_id.move_line_ids.product_id.ids)]

    def _compute_totals(self):
        for w in self:
            lines = w._target_move_lines()
            tokens = _tokenize_serials(w.paste_text)
            w.total_needed = sum(self._line_qty_target(l) for l in lines)
            w.total_entered = len(tokens)
            w.entered_serials_preview = "\n".join(tokens)

    @api.model
    def _line_qty_target(self, ml):
        qty = getattr(ml, 'qty_done', 0.0) or getattr(ml, 'quantity', 0.0) or 0.0
        if not qty:
            qty = getattr(ml, "reserved_uom_qty", 0.0) or getattr(ml, "reserved_quantity", 0.0) or 0.0
        if not qty and ml.move_id:
            qty = ml.move_id.product_uom_qty or 0.0
        return int(round(qty))

    def _compute_demand_qty_line(self):
        for w in self:
            qty = 0.0
            ml = w.move_line_id
            if ml and ml.move_id and 'product_uom_qty' in ml.move_id._fields:
                qty = ml.move_id.product_uom_qty or 0.0
            w.demand_qty_line = qty

    def _target_move_lines(self):
        self.ensure_one()
        if self.move_line_id:
            return self.move_line_id
        mls = self.picking_id.move_line_ids
        if self.only_unassigned:
            mls = mls.filtered(lambda ml: self._line_qty_target(ml) > len(ml.serial_captured_ids))
        if self.mode == "product" and self.product_id:
            mls = mls.filtered(lambda ml: ml.product_id.id == self.product_id.id)
        return mls.sorted(lambda ml: (ml.sequence, ml.id))

    def action_apply(self):
        self.ensure_one()
        if self.mode == "product" and not self.product_id:
            raise UserError(_("Debes seleccionar un producto cuando el modo es 'Aplicar a un producto específico'."))

        serials = _tokenize_serials(self.paste_text)
        lines = self._target_move_lines()

        needed = sum(self._line_qty_target(ml) for ml in lines)
        if not self.allow_mismatch:
            if len(serials) != needed:
                raise UserError(_("La cantidad de números de serie (%s) no coincide con las piezas objetivo (%s).") % (len(serials), needed))
            if not serials:
                raise UserError(_("No se proporcionaron números de serie."))

        # Limpiar existentes si así se indica
        if self.clear_existing:
            self.env["stock.move.line.serial"].search([("move_line_id", "in", lines.ids)]).unlink()

        # Duplicados en la entrada
        seen, dups = set(), set()
        for s in serials:
            if s in seen:
                dups.add(s)
            seen.add(s)
        if dups:
            if len(dups) == 1:
                raise UserError(_("Número de serie duplicado en la entrada: '%s'") % list(dups)[0])
            else:
                raise UserError(_("Duplicados en la entrada: %s") % (", ".join("'%s'" % x for x in sorted(dups))))

        # Duplicados ya guardados en la misma operación
        if serials:
            already = self.env['stock.move.line.serial'].search([
                ('picking_id', '=', self.picking_id.id),
                ('name', 'in', serials)
            ])
            if already:
                names = sorted(set(already.mapped('name')))
                if len(names) == 1:
                    raise UserError(_("El número de serie '%s' ya existe en esta operación.") % names[0])
                else:
                    raise UserError(_("Los siguientes números de serie ya existen en esta operación: %s") % ", ".join("'%s'" % n for n in names))

        # Duplicados globales en otras operaciones
        if serials and self.check_global_duplicate:
            other = self.env['stock.move.line.serial'].search([
                ('picking_id', '!=', self.picking_id.id),
                ('name', 'in', serials)
            ], limit=100)
            if other:
                byname = {}
                for rec in other:
                    byname.setdefault(rec.name, set()).add(rec.picking_id.display_name)
                parts = []
                for name in sorted(byname.keys()):
                    ops = ", ".join(sorted(byname[name]))
                    parts.append("'%s' en %s" % (name, ops))
                raise UserError(_("Duplicado global: los siguientes números ya existen en otras operaciones: %s") % "; ".join(parts))

        # Asignación
        to_create, s_idx = [], 0
        for ml in lines:
            qty_target = self._line_qty_target(ml)
            assign_n = min(qty_target, len(serials) - s_idx) if self.allow_mismatch else qty_target
            for i in range(assign_n):
                to_create.append({"name": serials[s_idx], "move_line_id": ml.id})
                s_idx += 1
                if s_idx >= len(serials):
                    break
            if s_idx >= len(serials):
                break

        if not to_create and serials:
            raise UserError(_("No se pudo asignar ningún número de serie. Verifique el alcance y cantidades."))

        mismatch = (len(serials) != needed)
        if mismatch and self.allow_mismatch:
            msg = _("Se capturaron %s de %s números de serie. Puedes completar los faltantes más tarde.") % (len(serials), needed)
            if hasattr(self.env.user, 'notify_warning'):
                self.env.user.notify_warning(message=msg, title=_("Advertencia"), sticky=False)
            elif hasattr(self.env.user, 'notify_info'):
                self.env.user.notify_info(message=msg, title=_("Advertencia"), sticky=False)

        self.env["stock.move.line.serial"].create(to_create)
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "view_mode": "form",
            "res_id": self.picking_id.id,
            "target": "current",
        }
