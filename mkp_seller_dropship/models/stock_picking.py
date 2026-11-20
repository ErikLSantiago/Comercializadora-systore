# -*- coding: utf-8 -*-
from odoo import models

class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        res = super().button_validate()

        for picking in self:
            if picking._mkp_is_dropship_like():
                sale_order = picking._mkp_get_related_sale_order()
                if sale_order:
                    sale_order._mkp_on_seller_delivery_completed()
        return res

    # -----------------
    # Helpers
    # -----------------
    def _mkp_is_dropship_like(self):
        """Detecta el picking de Dropship (Triangular).
        En tu caso el 'Documento origen' puede ser la PO, así que no usamos origin para detectar.
        Usamos:
        - picking_type.code == dropship (si existe)
        - o ubicaciones supplier -> customer
        """
        self.ensure_one()
        try:
            if self.location_id.usage == "supplier" and self.location_dest_id.usage == "customer":
                return True
        except Exception:
            pass
        if self.picking_type_id and self.picking_type_id.code == "dropship":
            return True
        sale_order = self._mkp_get_related_sale_order()
        return bool(sale_order and sale_order._mkp_get_seller())

    def _mkp_get_related_sale_order(self):
        """Obtiene la SO desde los stock.moves (lo más confiable en dropship).
        En muchos casos `origin` del picking es la PO (P00007), no la SO.
        """
        self.ensure_one()

        # 1) Desde moves -> sale_line_id -> order_id
        for mv in (self.move_ids or self.move_ids_without_package):
            sl = getattr(mv, "sale_line_id", False)
            if sl and sl.order_id:
                return sl.order_id

        # 2) Desde move_lines -> move -> sale_line_id
        for ml in self.move_line_ids:
            mv = getattr(ml, "move_id", False)
            sl = getattr(mv, "sale_line_id", False) if mv else False
            if sl and sl.order_id:
                return sl.order_id

        # 3) Fallback por origin si trae SO
        if self.origin:
            so = self.env["sale.order"].search([("name","=", self.origin)], limit=1)
            if so:
                return so
            so = self.env["sale.order"].search([("name","ilike", self.origin)], limit=1)
            if so:
                return so
        return False
