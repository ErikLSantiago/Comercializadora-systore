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
        """Compute price_unit based on selected lots and weight-based price.

        We also set the line description to include the selected lot/serial numbers so the
        customer can understand why the amount changes.
        """
        for line in self:
            tmpl = line.product_id.product_tmpl_id
            if not getattr(tmpl, 'x_use_weight_sale_price', False):
                continue

            # Ensure recordset
            if isinstance(lots, list):
                lots = line.env['stock.lot'].browse([l.id if hasattr(l, 'id') else int(l) for l in lots])

            lots = lots.exists()
            if not lots:
                continue

            price_per_weight = getattr(tmpl, 'x_weight_sale_price', 0.0) or 0.0
            if not price_per_weight:
                continue

            # Sum real weights from lots (expected field from meat_cutting / weight module)
            total_weight = sum((getattr(l, 'x_weight_kg', 0.0) or 0.0) for l in lots)
            if not total_weight:
                continue

            # unit price is the *total* line price divided by qty pieces
            qty = line.product_uom_qty or 1.0
            total_price = total_weight * price_per_weight
            line.price_unit = total_price / qty

            # Put lot numbers in the line description (safe for web + backend)
            lot_names = ', '.join(lots.mapped('name'))
            base_lines = (line.name or '').splitlines()
            # remove previous "Lotes:" line if exists
            base_lines = [l for l in base_lines if not l.strip().lower().startswith('lotes:')]
            base_name = '\n'.join(base_lines).strip()
            line.name = (base_name + ('\nLotes: %s' % lot_names)).strip()


