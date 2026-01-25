from odoo import api, fields, models, _
from odoo.tools.float_utils import float_is_zero


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    x_reserved_weight_kg = fields.Float(string="Peso reservado (kg)", readonly=True, copy=False)
    x_reserved_serial_count = fields.Integer(string="Seriales reservados", readonly=True, copy=False)
    x_reserved_serials_text = fields.Char(string="Seriales reservados", readonly=True, copy=False)

    def _mc_get_reserved_serial_move_lines(self):
        """Devuelve move lines (stock.move.line) con lot/serial asignado para esta línea.
        Importante: NO filtramos por destino 'customer' porque tu flujo puede ser a ubicaciones internas (empaque/calidad).
        """
        self.ensure_one()
        moves = self.move_ids.filtered(lambda m: m.state not in ("cancel",))
        mls = moves.mapped("move_line_ids").filtered(lambda ml: ml.lot_id)
        return mls

    def _mc_recompute_price_from_reserved_serials(self):
        self.ensure_one()
        tmpl = self.product_id.product_tmpl_id
        if not tmpl.x_use_weight_sale_price:
            return False

        # Necesitamos precio por kg
        if float_is_zero(tmpl.x_weight_sale_price or 0.0, precision_rounding=0.000001):
            return False

        mls = self._mc_get_reserved_serial_move_lines()
        if not mls:
            return False

        lots = mls.mapped("lot_id")
        weights = lots.mapped("x_weight_kg") if "x_weight_kg" in lots._fields else []
        total_weight = sum([w or 0.0 for w in weights])

        if float_is_zero(total_weight, precision_rounding=0.000001):
            return False

        # Precio por KG (asumimos unidad kg por ahora; el campo de UoM queda para futura expansión)
        price_per_kg = tmpl.x_weight_sale_price

        total_price = total_weight * price_per_kg

        # Cantidad en la línea (unidades)
        qty = self.product_uom_qty or 0.0
        if float_is_zero(qty, precision_rounding=self.product_uom.rounding):
            return False

        new_price_unit = total_price / qty

        # Guardar trazas
        self.x_reserved_weight_kg = total_weight
        self.x_reserved_serial_count = len(lots)
        self.x_reserved_serials_text = ", ".join(lots.mapped("name"))[:255]

        # Actualizar precio unitario
        self.price_unit = new_price_unit
        return True


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_recompute_weight_prices(self):
        """Botón manual: recalcula precio por peso según seriales (lot) asignados en las entregas."""
        for order in self:
            lines = order.order_line.filtered(lambda l: l.product_id and l.product_id.product_tmpl_id.x_use_weight_sale_price)
            for line in lines:
                line._mc_recompute_price_from_reserved_serials()
        return True
