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
            qty = getattr(mv, 'quantity_done', 0.0) or mv.product_uom_qty
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
        # Nota: el wizard se ejecuta ANTES de cerrar la MO, por lo que normalmente
        # aún no existen SVLs en los movimientos de consumo. Por eso:
        # 1) si ya hay SVL en el move (caso raro / reintentos), se usa.
        # 2) si no hay SVL, se estima el costo FIFO desde las capas disponibles (remaining_qty/value).
        StockValLayer = self.env["stock.valuation.layer"]

        def _move_qty_in_product_uom(move):
            """Obtiene la cantidad relevante del move en la UoM del producto."""
            qty = 0.0
            # En Odoo 19 los campos han cambiado entre modelos; tomamos el primero que exista.
            for fname in ("quantity", "quantity_done", "product_uom_qty"):
                if fname in move._fields:
                    qty = float(getattr(move, fname) or 0.0)
                    if qty:
                        break
            return move.product_uom._compute_quantity(qty, move.product_id.uom_id, rounding_method="HALF-UP")

        consumed_value = 0.0
        for mv in prod.move_raw_ids.filtered(lambda m: m.state != "cancel"):
            if mv.stock_valuation_layer_ids:
                consumed_value += sum(mv.stock_valuation_layer_ids.mapped("value"))
                continue

            qty_to_consume = _move_qty_in_product_uom(mv)
            if qty_to_consume <= 0:
                continue

            # FIFO: tomar capas con qty restante
            layers = StockValLayer.search(
                [
                    ("product_id", "=", mv.product_id.id),
                    ("company_id", "=", mv.company_id.id),
                    ("remaining_qty", ">", 0),
                ],
                order="create_date,id",
            )
            remaining = qty_to_consume
            for layer in layers:
                if remaining <= 0:
                    break
                take = min(remaining, layer.remaining_qty)
                # Valor proporcional
                unit_val = (layer.remaining_value / layer.remaining_qty) if layer.remaining_qty else 0.0
                consumed_value += take * unit_val
                remaining -= take

            # Si no alcanzan las capas, dejamos que el validado posterior lo detenga.

        return abs(consumed_value)

# Cerrar OF (evitar loop y saltar wizard)
        ctx = dict(self.env.context, cw_from_wizard=True)
        prod = prod.with_context(ctx)
        prod.write({"date_finished": self.production_date})
        prod.button_mark_done()

        # Seguridad: en algunos flujos Odoo no termina de procesar los movimientos creados por el wizard.
        # Forzamos a que los movimientos de terminado y subproducto queden en DONE si siguen pendientes.
        pending_moves = (prod.move_finished_ids | prod.move_byproduct_ids).filtered(lambda m: m.state not in ("done", "cancel"))
        if pending_moves:
            pending_moves._action_confirm()
            pending_moves._action_done()
        return {"type": "ir.actions.act_window_close"} 
