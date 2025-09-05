
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SerialCaptureWizard(models.TransientModel):
    _name = "serial.capture.wizard"
    _description = "Capturar números de serie (producto)"

    picking_id = fields.Many2one("stock.picking", string="Operación", required=True, readonly=True)
    product_id = fields.Many2one("product.product", string="Producto", required=True)
    demand_qty = fields.Float(string="Demanda", compute="_compute_totals", readonly=True)
    reserved_qty = fields.Float(string="Reservado", compute="_compute_totals", readonly=True)
    existing_serials_info = fields.Text(string="Seriales ya capturados", compute="_compute_existing", readonly=True)
    input_serials_text = fields.Text(string="Pegar/Escribir N° de serie (uno por línea)", required=True,
                                     help="Puedes pegar múltiples seriales, uno por línea.")

    @api.depends("picking_id", "product_id")
    def _compute_totals(self):
        for w in self:
            demand = 0.0
            reserved = 0.0
            if w.picking_id and w.product_id:
                for m in w.picking_id.move_ids_without_package.filtered(lambda x: x.product_id == w.product_id):
                    demand += m.product_uom_qty
                    # usar qty_reserved si existe en v18; si no, cae en 0
                    reserved += getattr(m, "reserved_uom_qty", 0.0) or getattr(m, "reserved_quantity", 0.0) or 0.0
            w.demand_qty = demand
            w.reserved_qty = reserved

    @api.depends("picking_id", "product_id")
    def _compute_existing(self):
        Serial = self.env["stock.move.line.serial"]
        for w in self:
            info = ""
            if w.picking_id and w.product_id:
                rows = Serial.search([("picking_id", "=", w.picking_id.id),
                                      ("product_id", "=", w.product_id.id)], order="id desc")
                if rows:
                    info = "\n".join(r.name for r in rows)
            w.existing_serials_info = info

    def _parse_serials(self, text):
        serials = []
        for raw in (text or "").splitlines():
            s = raw.strip()
            if s:
                serials.append(s)
        return serials

    def action_apply(self):
        self.ensure_one()
        serials = self._parse_serials(self.input_serials_text)

        # Duplicados locales
        seen = set()
        dups_local = set()
        for s in serials:
            if s in seen:
                dups_local.add(s)
            seen.add(s)
        if dups_local:
            raise UserError(_("Se encontraron números de serie duplicados en la entrada: %s") % ", ".join(sorted(dups_local)))

        # Duplicados globales en todo el sistema
        Serial = self.env["stock.move.line.serial"]
        existing = Serial.search([("name", "in", serials)])
        if existing:
            raise UserError(_("Los siguientes números de serie ya existen en el sistema: %s") % ", ".join(sorted(set(existing.mapped("name")))))

        # Distribuir sobre líneas (si hay)
        move_lines = self.picking_id.move_line_ids.filtered(lambda ml: ml.product_id == self.product_id)
        # Si no hay líneas de operación, igualmente guardamos con move_line_id vacío
        by_ml_count = {ml.id: self.env["stock.move.line.serial"].search_count([("move_line_id", "=", ml.id)]) for ml in move_lines}
        for s in serials:
            # escoger la ml con menos seriales ligados hasta ahora
            ml_target = None
            if move_lines:
                ml_target = min(move_lines, key=lambda ml: by_ml_count.get(ml.id, 0))
                by_ml_count[ml_target.id] = by_ml_count.get(ml_target.id, 0) + 1
            Serial.create({
                "name": s,
                "product_id": self.product_id.id,
                "picking_id": self.picking_id.id,
                "move_line_id": ml_target and ml_target.id or False,
                "lot_id": ml_target and getattr(ml_target, "lot_id", False) and ml_target.lot_id.id or False,
            })

        # cerrar wizard y refrescar vista
        return {
            "type": "ir.actions.act_window",
            "res_model": "serial.capture.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_picking_id": self.picking_id.id,
                "default_product_id": self.product_id.id,
            },
        }
