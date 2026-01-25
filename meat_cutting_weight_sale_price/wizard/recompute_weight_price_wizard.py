from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero


class MeatCuttingRecomputeWeightPriceWizard(models.TransientModel):
    _name = "mc.weight.price.wizard"
    _description = "Recalcular precio por peso (por serial)"

    sale_order_id = fields.Many2one("sale.order", required=True, ondelete="cascade")
    line_id = fields.Many2one(
        "sale.order.line",
        string="Línea a dividir",
        domain="[('order_id', '=', sale_order_id)]",
        required=True,
    )
    # Seriales/lotes a vender (uno por pieza)
    lot_ids = fields.Many2many(
        "stock.lot",
        string="Seriales / Lotes",
        help="Selecciona las piezas (seriales) que se venderán en esta línea. Se creará una línea por cada serial.",
        domain="[('product_id', '=', product_id)]",
    )

    product_id = fields.Many2one(related="line_id.product_id", store=False, readonly=True)

    price_per_weight = fields.Float(string="Precio por peso", readonly=True)
    price_weight_uom_id = fields.Many2one("uom.uom", string="Unidad", readonly=True)

    @api.onchange("line_id")
    def _onchange_line_id(self):
        for wiz in self:
            wiz.lot_ids = [(5, 0, 0)]
            if not wiz.line_id:
                wiz.price_per_weight = 0.0
                wiz.price_weight_uom_id = False
                continue
            tmpl = wiz.line_id.product_id.product_tmpl_id
            wiz.price_per_weight = tmpl.x_price_per_weight or 0.0
            wiz.price_weight_uom_id = tmpl.x_price_weight_uom_id

    def _convert_weight_to_uom(self, weight_kg, target_uom):
        """Convert kg -> target uom (kg or g typically)."""
        self.ensure_one()
        if not target_uom:
            return weight_kg
        # Use UoM conversion using reference unit from the uom category.
        # We assume weight_kg is in KG. Convert KG -> target_uom.
        kg_uom = self.env.ref("uom.product_uom_kgm", raise_if_not_found=False)
        if not kg_uom:
            # Fallback: treat as kg
            return weight_kg
        return kg_uom._compute_quantity(weight_kg, target_uom)

    def action_apply(self):
        self.ensure_one()
        so = self.sale_order_id
        line = self.line_id

        if not line or line.order_id != so:
            raise UserError(_("Selecciona una línea válida."))

        tmpl = line.product_id.product_tmpl_id
        if not tmpl.x_use_weight_sale_price:
            raise UserError(_("Este producto no está configurado para usar precio por peso (reserva)."))

        if float_is_zero(tmpl.x_price_per_weight or 0.0, precision_rounding=0.000001):
            raise UserError(_("Configura 'Precio en peso' en el producto."))

        if not tmpl.x_price_weight_uom_id:
            raise UserError(_("Configura la 'Unidad precio por peso' en el producto (KG o g)."))

        if not self.lot_ids:
            raise UserError(_("Selecciona al menos un serial/lote."))

        # Validar peso por serial
        missing = self.lot_ids.filtered(lambda l: float_is_zero(getattr(l, "x_weight_kg", 0.0) or 0.0, precision_rounding=0.000001))
        if missing:
            raise UserError(_("Estos seriales no tienen peso (x_weight_kg): %s") % ", ".join(missing.mapped("name")))

        # Creamos una línea por serial (qty=1), copiando condiciones comerciales
        new_lines_vals = []
        for lot in self.lot_ids:
            weight_kg = float(lot.x_weight_kg or 0.0)
            weight_in_uom = self._convert_weight_to_uom(weight_kg, tmpl.x_price_weight_uom_id)
            price = (tmpl.x_price_per_weight or 0.0) * weight_in_uom

            # Name includes weight + lot for traceability in SO & invoice
            name = "%s (%0.3f KG - %s)" % (line.name or line.product_id.display_name, weight_kg, lot.name)

            vals = {
                "order_id": so.id,
                "product_id": line.product_id.id,
                "product_uom_qty": 1.0,
                "product_uom": line.product_uom.id,
                "price_unit": price,
                "discount": line.discount,
                "tax_id": [(6, 0, line.tax_id.ids)],
                "name": name,
            }
            # copy analytic tags if present
            if "analytic_distribution" in line._fields:
                vals["analytic_distribution"] = line.analytic_distribution
            if "analytic_tag_ids" in line._fields:
                vals["analytic_tag_ids"] = [(6, 0, line.analytic_tag_ids.ids)]
            # custom field to store chosen lot
            if "x_sale_lot_id" in line._fields:
                vals["x_sale_lot_id"] = lot.id

            new_lines_vals.append(vals)

        # Remove original line and replace
        # Safety: only allow when line not yet invoiced to avoid accounting inconsistencies
        if line.qty_invoiced and not float_is_zero(line.qty_invoiced, precision_rounding=line.product_uom.rounding):
            raise UserError(_("No se puede dividir una línea ya facturada. Crea una nueva orden o línea."))

        line.unlink()
        self.env["sale.order.line"].create(new_lines_vals)

        # Recompute totals (Odoo 17+ uses _compute_amounts)
        if hasattr(so, "_compute_amounts"):
            so._compute_amounts()
        elif hasattr(so, "_amount_all"):
            so._amount_all()
        else:
            # Fallback: recompute stored fields lazily
            so.invalidate_recordset()

        return {"type": "ir.actions.act_window_close"}
