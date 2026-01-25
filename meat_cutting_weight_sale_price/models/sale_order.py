from odoo import fields, models, _
from odoo.tools.float_utils import float_is_zero


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    x_reserved_weight_kg = fields.Float(string="Peso reservado (kg)", readonly=True, copy=False)
    x_reserved_serial_count = fields.Integer(string="Seriales reservados", readonly=True, copy=False)
    x_reserved_serials_text = fields.Char(string="Seriales reservados", readonly=True, copy=False)

    def _mc_get_reserved_serial_move_lines(self):
        """Move lines con serial asignado ligados a esta línea (sin filtrar por ubicación destino)."""
        self.ensure_one()
        moves = self.move_ids.filtered(lambda m: m.state not in ("cancel",))
        return moves.mapped("move_line_ids").filtered(lambda ml: ml.lot_id)

    def _mc_recompute_price_from_reserved_serials(self):
        """Recalcula price_unit según peso real (lot.x_weight_kg) de los seriales reservados."""
        self.ensure_one()
        tmpl = self.product_id.product_tmpl_id

        if not getattr(tmpl, "x_use_weight_sale_price", False):
            return False

        price_per_weight = getattr(tmpl, "x_price_per_weight", 0.0) or 0.0
        if float_is_zero(price_per_weight, precision_rounding=0.000001):
            return False

        mls = self._mc_get_reserved_serial_move_lines()
        if not mls:
            return False

        lots = mls.mapped("lot_id")
        if "x_weight_kg" not in lots._fields:
            return False

        total_weight_kg = sum([w or 0.0 for w in lots.mapped("x_weight_kg")])
        if float_is_zero(total_weight_kg, precision_rounding=0.000001):
            return False

        # Convertir según UoM configurada (kg por defecto; si es "g" entonces kg->g)
        uom = getattr(tmpl, "x_price_weight_uom_id", False)
        weight_in_uom = total_weight_kg
        if uom and getattr(uom, "name", "") and uom.name.strip().lower() in ("g", "gram", "gramo", "gramos"):
            weight_in_uom = total_weight_kg * 1000.0

        total_price = weight_in_uom * price_per_weight

        qty = self.product_uom_qty or 0.0
        if float_is_zero(qty, precision_rounding=self.product_uom.rounding):
            return False

        new_price_unit = total_price / qty

        self.x_reserved_weight_kg = total_weight_kg
        self.x_reserved_serial_count = len(lots)
        self.x_reserved_serials_text = ", ".join(lots.mapped("name"))[:255]
        self.price_unit = new_price_unit
        return True


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_recompute_weight_prices(self):
        """Botón manual: recalcula precio por peso para líneas marcadas."""
        for order in self:
            lines = order.order_line.filtered(
                lambda l: l.product_id and getattr(l.product_id.product_tmpl_id, "x_use_weight_sale_price", False)
            )
            for line in lines:
                line._mc_recompute_price_from_reserved_serials()
        return True
