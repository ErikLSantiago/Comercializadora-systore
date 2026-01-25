from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import timedelta

class MrpCwFinishWizardLine(models.TransientModel):
    _name = "mrp.cw.finish.wizard.line"
    _description = "Catch Weight Finish Line"

    wizard_id = fields.Many2one("mrp.cw.finish.wizard", required=True, ondelete="cascade")
    weight_g = fields.Integer("Peso (g)", required=True)
    qty_units = fields.Integer("Cantidad (unidades)", required=True, default=1)
    is_waste = fields.Boolean("Es merma", default=False)

class MrpCwFinishWizard(models.TransientModel):
    _name = "mrp.cw.finish.wizard"
    _description = "Catch Weight Finish Wizard"

    production_id = fields.Many2one("mrp.production", required=True, readonly=True)
    production_date = fields.Datetime("Fecha de producción", required=True, default=fields.Datetime.now)

    line_ids = fields.One2many("mrp.cw.finish.wizard.line", "wizard_id", string="Detalle por peso")
    waste_product_id = fields.Many2one("product.product", string="Producto Merma", domain=[("type","=","product")])

    consumed_weight_g = fields.Integer("Consumido (g)", compute="_compute_totals")
    produced_good_weight_g = fields.Integer("Bueno (g)", compute="_compute_totals")
    waste_weight_g = fields.Integer("Merma (g)", compute="_compute_totals")
    diff_weight_g = fields.Integer("Diferencia (g)", compute="_compute_totals")

    @api.depends("line_ids.weight_g", "line_ids.qty_units", "line_ids.is_waste", "production_id")
    def _compute_totals(self):
        for w in self:
            consumed_g = w._compute_consumed_weight_g()
            good_g = sum(l.weight_g * l.qty_units for l in w.line_ids if not l.is_waste)
            waste_g = sum(l.weight_g * l.qty_units for l in w.line_ids if l.is_waste)
            w.consumed_weight_g = consumed_g
            w.produced_good_weight_g = good_g
            w.waste_weight_g = waste_g
            w.diff_weight_g = consumed_g - (good_g + waste_g)

    def _get_uom_gram_in_weight_category(self):
        self.ensure_one()
        prod = self.production_id
        raw_moves = prod.move_raw_ids.filtered(lambda m: m.state != "cancel" and m.product_uom)
        if not raw_moves:
            raise UserError(_("No hay movimientos de consumo para inferir la categoría de peso."))

        weight_category = raw_moves[0].product_uom.category_id
        Uom = self.env["uom.uom"]

        uom_g = Uom.search([
            ("category_id", "=", weight_category.id),
            ("name", "in", ["g", "gram", "grams", "Gramo", "Gramos", "Gram", "Grams"]),
        ], limit=1)

        if not uom_g:
            # fallback: detectar por factor cercano a gramos (si referencia es kg)
            cand = Uom.search([("category_id", "=", weight_category.id)], limit=200)
            uom_g = cand.filtered(lambda u: abs((u.factor or 0.0) - 0.001) < 1e-9 or abs((u.factor_inv or 0.0) - 1000.0) < 1e-6)[:1]

        if not uom_g:
            raise UserError(_(
                "No se encontró la unidad 'g' (gramos) en la categoría de peso '%s'. "
                "Activa o crea 'g' en esa categoría."
            ) % weight_category.display_name)

        return uom_g[0], weight_category

    def _compute_consumed_weight_g(self):
        self.ensure_one()
        prod = self.production_id
        uom_g, weight_category = self._get_uom_gram_in_weight_category()

        consumed_g = 0.0
        for mv in prod.move_raw_ids.filtered(lambda m: m.state != "cancel"):
            if mv.product_uom.category_id != weight_category:
                raise UserError(_("UoM del consumo '%s' no pertenece a la categoría de peso.") % mv.display_name)
            qty = mv.quantity_done or mv.product_uom_qty
            qty_g = mv.product_uom._compute_quantity(qty, uom_g)
            consumed_g += qty_g

        return int(round(consumed_g))

    def _convert_g_to_uom(self, grams_int, target_uom, weight_category):
        uom_g, _ = self._get_uom_gram_in_weight_category()
        if target_uom.category_id != weight_category:
            raise UserError(_("La UoM destino no está en la categoría de peso."))
        return uom_g._compute_quantity(float(grams_int), target_uom)

    def _get_consumed_value_fifo(self):
        self.ensure_one()
        prod = self.production_id
        consumed_value = 0.0
        for mv in prod.move_raw_ids.filtered(lambda m: m.state != "cancel"):
            consumed_value += sum(mv.stock_valuation_layer_ids.mapped("value"))
        return abs(consumed_value)

    def _get_or_create_lot(self, product, weight_g, prod_date):
        sku = product.default_code or str(product.id)
        date_str = fields.Datetime.to_datetime(prod_date).strftime("%Y%m%d")
        lot_name = f"{sku}-{int(weight_g):03d}G-{date_str}"

        lot = self.env["stock.lot"].search([("name", "=", lot_name), ("product_id", "=", product.id)], limit=1)
        if lot:
            # Asegurar peso guardado
            if not lot.x_weight_g:
                lot.x_weight_g = int(weight_g)
            return lot

        vals = {"name": lot_name, "product_id": product.id, "x_weight_g": int(weight_g)}
        days = product.product_tmpl_id.x_shelf_life_days or 0
        if days:
            exp = fields.Datetime.to_datetime(prod_date) + timedelta(days=days)
            if "expiration_date" in self.env["stock.lot"]._fields:
                vals["expiration_date"] = exp
            elif "use_date" in self.env["stock.lot"]._fields:
                vals["use_date"] = exp
        return self.env["stock.lot"].create(vals)

    def _replace_finished_moves_by_weight(self, consumed_value):
        self.ensure_one()
        prod = self.production_id
        finished_product = prod.product_id

        good_weight_g = sum(l.weight_g * l.qty_units for l in self.line_ids.filtered(lambda x: not x.is_waste and x.qty_units > 0))
        if good_weight_g <= 0:
            raise UserError(_("El peso producido bueno debe ser > 0."))

        cost_per_g = consumed_value / float(good_weight_g)

        # Cancelar moves anteriores del terminado (si existen)
        old_moves = prod.move_finished_ids.filtered(lambda m: m.product_id == finished_product and m.state != "cancel")
        if old_moves:
            old_moves._action_cancel()

        created_moves = self.env["stock.move"]
        total_units = 0.0

        for l in self.line_ids.filtered(lambda x: not x.is_waste and x.qty_units > 0):
            lot = self._get_or_create_lot(finished_product, l.weight_g, self.production_date)
            unit_cost = float(l.weight_g) * cost_per_g  # costo por pieza según peso
            qty_units = float(l.qty_units)

            mv = self.env["stock.move"].create({
                "name": finished_product.display_name,
                "product_id": finished_product.id,
                "product_uom": finished_product.uom_id.id,
                "product_uom_qty": qty_units,
                "location_id": prod.location_src_id.id,
                "location_dest_id": prod.location_dest_id.id,
                "production_id": prod.id,
                "company_id": prod.company_id.id,
                "date": self.production_date,
                "price_unit": unit_cost,
            })

            self.env["stock.move.line"].create({
                "move_id": mv.id,
                "product_id": finished_product.id,
                "product_uom_id": finished_product.uom_id.id,
                "qty_done": qty_units,
                "lot_id": lot.id,
                "location_id": prod.location_src_id.id,
                "location_dest_id": prod.location_dest_id.id,
            })

            created_moves |= mv
            total_units += qty_units

        # Ajustar cantidad producida planificada a lo realmente producido (para cerrar limpio)
        prod.product_qty = total_units
        return created_moves, cost_per_g

    def action_apply_and_mark_done(self):
        self.ensure_one()
        prod = self.production_id
        finished_product = prod.product_id

        if not finished_product.product_tmpl_id.x_is_catch_weight:
            raise UserError(_("Este producto no está configurado como Catch Weight."))

        good_g = sum(l.weight_g * l.qty_units for l in self.line_ids if not l.is_waste)
        waste_g = sum(l.weight_g * l.qty_units for l in self.line_ids if l.is_waste)

        consumed_g = self._compute_consumed_weight_g()
        diff = consumed_g - (good_g + waste_g)
        if diff != 0:
            raise UserError(_(
                "Diferencia de peso. Ajusta líneas (incluye merma) para cerrar sin diferencia.\n\n"
                "Consumido: %(c)s g\n"
                "Bueno: %(g)s g\n"
                "Merma: %(w)s g\n"
                "Diferencia: %(d)s g"
            ) % {"c": consumed_g, "g": good_g, "w": waste_g, "d": diff})

        consumed_value = self._get_consumed_value_fifo()
        if not consumed_value:
            raise UserError(_("No se pudo determinar el costo consumido (SVL=0). Revisa valuación automática."))

        # Crear moves terminados por peso/lote
        self._replace_finished_moves_by_weight(consumed_value)

        # Merma inventariable (by-product) con price_unit=0
        if waste_g > 0:
            if not self.waste_product_id:
                raise UserError(_("Hay merma pero no seleccionaste el producto de merma."))

            uom_g, weight_cat = self._get_uom_gram_in_weight_category()
            waste_qty_in_uom = self._convert_g_to_uom(int(waste_g), self.waste_product_id.uom_id, weight_cat)

            waste_move = prod.move_byproduct_ids.filtered(lambda m: m.product_id == self.waste_product_id and m.state != "cancel")
            if waste_move:
                waste_move = waste_move[0]
                waste_move.move_line_ids.unlink()
            else:
                waste_move = self.env["stock.move"].create({
                    "name": _("Merma"),
                    "product_id": self.waste_product_id.id,
                    "product_uom": self.waste_product_id.uom_id.id,
                    "product_uom_qty": waste_qty_in_uom,
                    "location_id": prod.location_src_id.id,
                    "location_dest_id": prod.location_dest_id.id,
                    "production_id": prod.id,
                    "company_id": prod.company_id.id,
                    "date": self.production_date,
                    "price_unit": 0.0,
                })

            self.env["stock.move.line"].create({
                "move_id": waste_move.id,
                "product_id": self.waste_product_id.id,
                "product_uom_id": waste_move.product_uom.id,
                "qty_done": waste_qty_in_uom,
                "location_id": waste_move.location_id.id,
                "location_dest_id": waste_move.location_dest_id.id,
            })

        # Cerrar OF (evitar loop y saltar wizard)
        ctx = dict(self.env.context, cw_from_wizard=True)
        prod = prod.with_context(ctx)
        prod.write({"date_finished": self.production_date})
        prod.button_mark_done()
        return {"type": "ir.actions.act_window_close"}
