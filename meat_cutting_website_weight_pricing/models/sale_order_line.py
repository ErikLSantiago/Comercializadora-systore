from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    x_web_reserved_lot_ids = fields.Many2many(
        comodel_name="stock.lot",
        relation="sale_order_line_mc_web_lot_rel",
        column1="sale_line_id",
        column2="lot_id",
        string="Lotes reservados (web)",
        help="Lotes/seriales seleccionados y reservados al llegar a checkout (paso de pago).",
        readonly=True,
        copy=False,
    )

    x_web_reserved_lot_display = fields.Char(
        string="Lotes reservados (web)",
        help="Se llena automáticamente cuando el cliente llega a checkout (paso de pago).",
        readonly=True,
        copy=False,
    )

    def mc_web_compute_price_from_lots(self, lots):
        """Compute unit price from the given reserved lots (recordset or list)."""
        self.ensure_one()

        # `lots` may come as a python list (records) or list of ids, convert to recordset.
        if isinstance(lots, list):
            if lots and isinstance(lots[0], int):
                lots = self.env['stock.lot'].browse(lots)
            else:
                lots = self.env['stock.lot'].browse([l.id for l in lots if getattr(l, 'id', None)])
        lots = lots.filtered(lambda l: l and l.exists())
        if not lots:
            return False

        tmpl = self.product_id.product_tmpl_id
        if not getattr(tmpl, "x_use_weight_sale_price", False):
            return False

        price_per_weight = getattr(tmpl, "x_weight_sale_price", 0.0) or 0.0
        price_uom = getattr(tmpl, "x_price_weight_uom_id", False)
        if not price_uom or not price_per_weight:
            return False

        total_kg = sum(lots.mapped("x_weight_kg") or [0.0])

        # Convert KG -> UoM configurada para precio
        kg_uom = self.env.ref("uom.product_uom_kgm", raise_if_not_found=False)
        if kg_uom and kg_uom.category_id != price_uom.category_id:
            kg_uom = False
        if not kg_uom:
            kg_uom = self.env["uom.uom"].search(
                [
                    ("category_id", "=", price_uom.category_id.id),
                    ("uom_type", "=", "reference"),
                ],
                limit=1,
            )

        qty_in_price_uom = kg_uom._compute_quantity(total_kg, price_uom) if kg_uom else total_kg

        currency = self.order_id.currency_id or self.env.company.currency_id
        total_price = currency.round(qty_in_price_uom * price_per_weight)

        qty = self.product_uom_qty or 0.0
        unit_price = total_price / qty if qty else total_price

        self.write({"price_unit": unit_price})
        return True
