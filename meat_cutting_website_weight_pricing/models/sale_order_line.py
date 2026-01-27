# -*- coding: utf-8 -*-
from odoo import api, fields, models

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    mc_web_lot_display = fields.Char(
        string="Unidad de peso asignada",
        compute="_compute_mc_web_lot_display",
        help="Número(s) de lote/serie asignado(s) en el checkout para explicar el precio final por peso."
    )

    @api.depends("order_id", "product_id", "product_uom_qty")
    def _compute_mc_web_lot_display(self):
        # Default
        for line in self:
            line.mc_web_lot_display = False

        # Preferimos la reserva (mc.web.reservation) si existe
        Reservation = self.env["mc.web.reservation"].sudo()
        reservations = Reservation.search([("order_line_id", "in", self.ids)])
        by_line = {}
        for r in reservations:
            by_line.setdefault(r.order_line_id.id, []).append(r.lot_id.display_name or r.lot_id.name)

        for line in self:
            names = by_line.get(line.id)
            if names:
                # Si hubiera varias piezas, mostramos todas separadas por coma
                line.mc_web_lot_display = ", ".join([n for n in names if n])
                continue

            # Fallback: si el módulo/instancia trae lot_id en la línea (algunas configuraciones lo agregan),
            # lo mostramos también.
            lot = getattr(line, "lot_id", False)
            if lot:
                line.mc_web_lot_display = lot.display_name or lot.name
