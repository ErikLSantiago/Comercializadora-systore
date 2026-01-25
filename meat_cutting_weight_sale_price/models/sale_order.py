from odoo import fields, models, _
from odoo.tools.float_utils import float_is_zero

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    x_reserved_weight_kg = fields.Float(string="Peso reservado (kg)", readonly=True, copy=False)
    x_reserved_serial_count = fields.Integer(string="Seriales reservados", readonly=True, copy=False)

    def _mc_get_reserved_serial_move_lines(self):
        self.ensure_one()
        # Moves de salida ligados a esta línea (entrega)
        moves = self.move_ids.filtered(lambda m: m.state not in ("cancel",) and m.location_dest_id.usage == "customer")
        mls = moves.mapped("move_line_ids").filtered(lambda ml: ml.lot_id)
        return mls

    def _mc_reserved_qty(self, ml):
        for fname in ("reserved_uom_qty", "quantity", "product_uom_qty"):
            if fname in ml._fields:
                return ml[fname] or 0.0
        return 0.0

    def _mc_recompute_price_from_reserved_serials(self):
        kg_uom = self.env.ref("uom.product_uom_kgm", raise_if_not_found=False)

        for line in self:
            tmpl = line.product_id.product_tmpl_id
            if not tmpl.x_use_weight_sale_price:
                continue
            if not tmpl.x_price_weight_uom_id or not kg_uom:
                continue
            price_per_weight = tmpl.x_price_per_weight or 0.0
            if float_is_zero(price_per_weight, precision_rounding=0.00001):
                continue

            mls = line._mc_get_reserved_serial_move_lines()
            total_weight_kg = 0.0
            serial_count = 0

            for ml in mls:
                qty = line._mc_reserved_qty(ml)
                if qty <= 0:
                    continue
                if not ml.lot_id.x_weight_kg:
                    continue
                total_weight_kg += (ml.lot_id.x_weight_kg * qty)
                serial_count += int(qty)

            if serial_count <= 0 or float_is_zero(total_weight_kg, precision_rounding=0.00001):
                line.write({"x_reserved_weight_kg": 0.0, "x_reserved_serial_count": 0})
                continue

            kg_per_unit = tmpl.x_price_weight_uom_id._compute_quantity(1.0, kg_uom)
            if float_is_zero(kg_per_unit, precision_rounding=0.00001):
                continue
            price_per_kg = price_per_weight / kg_per_unit

            total_price = total_weight_kg * price_per_kg
            price_unit = total_price / serial_count

            line.write({
                "price_unit": price_unit,
                "x_reserved_weight_kg": total_weight_kg,
                "x_reserved_serial_count": serial_count,
            })


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_recompute_weight_prices(self):
        """Botón manual: recalcula precio por peso según seriales reservados en la entrega."""
        for order in self:
            # Recalcular solo líneas marcadas
            lines = order.order_line.filtered(lambda l: l.product_id.product_tmpl_id.x_use_weight_sale_price)
            for line in lines:
                line._mc_recompute_price_from_reserved_serials()
        return True
