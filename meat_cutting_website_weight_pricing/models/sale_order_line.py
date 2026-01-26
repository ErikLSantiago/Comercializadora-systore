from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    x_web_reserved_lot_display = fields.Char(
        string="Lotes reservados (web)",
        help="Se llena automáticamente cuando el cliente llega a checkout (paso de pago) para explicar el precio exacto.",
        readonly=True,
        copy=False,
    )


    def mc_web_compute_price_from_lots(self, lots):
        """Recalcula precio unitario (por pieza) usando el peso real de los lotes/seriales.
        - lots: recordset stock.lot (típicamente seriales), cada uno con x_weight_kg
        """
        self.ensure_one()
        product = self.product_id
        tmpl = product.product_tmpl_id

        if not tmpl.x_use_weight_sale_price:
            return

        qty = self.product_uom_qty or 0.0
        if qty <= 0:
            return

        total_weight = sum(lots.mapped("x_weight_kg")) or 0.0
        price_per_kg = getattr(tmpl, 'x_price_per_weight', 0.0) or 0.0

        # Total a cobrar = peso_total * precio_por_kg
        total_price = total_weight * price_per_kg

        # Odoo guarda precio unitario por pieza: total / qty
        self.price_unit = total_price / qty
