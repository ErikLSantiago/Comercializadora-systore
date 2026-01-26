from odoo import models
from odoo.tools import float_compare


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _mc_web_get_reserved_qty(self):
        """Cantidad reservada (web) para este producto, basada en mc.web.reservation vigentes."""
        now = self.env["mc.web.reservation"]._now()
        domain = [("product_id", "in", self.ids), ("reserved_until", ">", now)]
        data = self.env["mc.web.reservation"].sudo().read_group(domain, ["product_id"], ["product_id"])
        return {d["product_id"][0]: d["product_id_count"] for d in data}

    def _get_combination_info_variant(self, *args, **kwargs):
        info = super()._get_combination_info_variant(*args, **kwargs)

        # En website, la disponibilidad se debe reducir por las reservas (web) para evitar que dos clientes
        # paguen/compitan por las mismas piezas.
        try:
            tmpl = self.product_tmpl_id
        except Exception:
            return info

        if not getattr(tmpl, "x_use_weight_sale_price", False):
            return info

        reserved_map = self._mc_web_get_reserved_qty()
        reserved_qty = reserved_map.get(self.id, 0) or 0

        for key in ("free_qty", "qty_available", "virtual_available"):
            if key in info and info[key] is not None:
                info[key] = max(0.0, info[key] - reserved_qty)

        return info
