# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class StockPicking(models.Model):
    _inherit = "stock.picking"

    # --- Wizard clásico para capturar seriales por líneas ---
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

    # --- Lista unificada por producto (Seriales - adicional) ---
    def action_open_serial_lines_list(self):
        self.ensure_one()
        import uuid as _uuid
        token = str(_uuid.uuid4())
        self._prepare_adicional_sn_product_rows(token)
        action = self.env.ref('adicional_serial_number.action_move_lines_by_picking_adicional_sn').read()[0]
        action['context'] = {'adicional_sn_token': token, 'default_picking_id': self.id}
        action['domain'] = [('session_token', '=', token), ('picking_id', '=', self.id)]
        return action

    def _prepare_adicional_sn_product_rows(self, session_token):
        self.ensure_one()
        T = self.env["adicional.sn.product.line"].sudo()
        # limpiar previos de este token/picking
        T.search([("session_token", "=", session_token), ("picking_id", "=", self.id)]).unlink()

        # agrupar por producto
        by_product = {}
        for ml in self.move_line_ids:
            prod = ml.product_id
            if not prod:
                continue
            rec = by_product.setdefault(prod.id, {
                "demand_total": 0.0,
                "reserved_total": 0.0,
            })
            # Demanda total desde el move
            if ml.move_id and "product_uom_qty" in ml.move_id._fields:
                rec["demand_total"] += (ml.move_id.product_uom_qty or 0.0)
            # Reservado (heurística robusta)
            qty_res = 0.0
            if "quantity" in ml._fields and (ml.quantity or 0.0):
                qty_res = ml.quantity or 0.0
            if not qty_res:
                qty_res = getattr(ml, "reserved_uom_qty", 0.0) or getattr(ml, "reserved_quantity", 0.0) or 0.0
            if not qty_res:
                qty_res = getattr(ml, "qty_done", 0.0) or 0.0
            rec["reserved_total"] += qty_res

        # seriales existentes por producto
        S = self.env["stock.move.line.serial"].sudo()
        existing = S.read_group(
            domain=[("picking_id", "=", self.id)],
            fields=["name", "product_id"],
            groupby=["product_id"],
        )
        captured_ids = set()
        for row in existing:
            pid = row.get("product_id") and row["product_id"][0]
            if pid:
                captured_ids.add(pid)

        records = []
        for pid, vals in by_product.items():
            records.append({
                "session_token": session_token,
                "picking_id": self.id,
                "product_id": pid,
                "demand_total": vals["demand_total"],
                "reserved_total": vals["reserved_total"],
                "captured_label": _("Capturado") if pid in captured_ids else "",
            })

        if records:
            T.create(records)
        return True

    # --- Totales para colorear el smart button ---
    serial_demand_total = fields.Integer(string="Demanda (seriales)", compute="_compute_serial_totals", store=False)
    serial_captured_count = fields.Integer(string="Seriales capturados", compute="_compute_serial_totals", store=False)

    @api.depends('move_ids_without_package.product_uom_qty', 'move_ids_without_package.product_id.tracking')
    def _compute_serial_totals(self):
        # conteo de seriales capturados por picking
        groups = self.env["stock.move.line.serial"].read_group(
            domain=[("picking_id", "in", self.ids)],
            fields=["picking_id"],
            groupby=["picking_id"],
        )
        map_counts = {g["picking_id"][0]: g["picking_id_count"] for g in groups}

        for p in self:
            demand = 0
            for m in p.move_ids_without_package:
                if m.product_id and m.product_id.tracking == 'serial':
                    demand += int(round(m.product_uom_qty or 0))
            p.serial_demand_total = demand
            p.serial_captured_count = map_counts.get(p.id, 0)

    # --- Acción del smart button ---
    def action_open_serial_captured_list(self):
        self.ensure_one()
        return {
            "name": _("Seriales capturados"),
            "type": "ir.actions.act_window",
            "res_model": "stock.move.line.serial",
            "view_mode": "list,form",
            "target": "current",
            "domain": [("picking_id", "=", self.id)],
            "context": {"search_default_picking_id": self.id, "default_picking_id": self.id},
        }
