from odoo import api, fields, models, _
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
        """Recalcula price_unit según peso real de los seriales reservados."""
        self.ensure_one()
        tmpl = self.product_id.product_tmpl_id

        if not tmpl.x_use_weight_sale_price:
            return False

        price_per_weight = tmpl.x_price_per_weight or 0.0
        if float_is_zero(price_per_weight, precision_rounding=0.000001):
            return False

        mls = self._mc_get_reserved_serial_move_lines()
        if not mls:
            return False

        lots = mls.mapped("lot_id")
        if "x_weight_kg" not in lots._fields:
            return False

        total_weight_kg = sum((lots.mapped("x_weight_kg")))  # pesos ya guardados en kg
        if float_is_zero(total_weight_kg, precision_rounding=0.000001):
            return False

        # Convertir peso según UoM configurada en el producto (por ahora soportamos kg y g)
        uom = tmpl.x_price_weight_uom_id
        if uom and uom.category_id and uom.category_id == self.env.ref("uom.product_uom_categ_kgm", raise_if_not_found=False):
            # Si el usuario puso precio por "g", convertir kg -> g
            if uom and uom.name and uom.name.lower() in ("g", "gram", "gramo", "gramos"):
                weight_in_uom = total_weight_kg * 1000.0
            else:
                weight_in_uom = total_weight_kg
        else:
            # Si no hay categoría o no es peso, asumir kg
            weight_in_uom = total_weight_kg

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
            lines = order.order_line.filtered(lambda l: l.product_id and l.product_id.product_tmpl_id.x_use_weight_sale_price)
            for line in lines:
                line._mc_recompute_price_from_reserved_serials()
        return True
