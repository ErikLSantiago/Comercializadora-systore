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

    company_id = fields.Many2one("res.company", related="production_id.company_id", readonly=True)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", readonly=True)
    cw_consumed_value = fields.Monetary(string="Valor consumido", currency_field="currency_id", readonly=True)


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

    def _make_lot_name(self, product, production_date, seq, weight_g=None):
        """Build a deterministic lot name for CW-produced items.

        We keep this stable across versions so lots can be traced easily.
        Format: <SKU>-<YYYYMMDD>-<SEQ4> (e.g. COSTILLAR-20260124-0001).
        """
        sku = (product.default_code or product.display_name or 'CW').replace(' ', '').upper()
        dt = fields.Datetime.to_datetime(production_date) if production_date else fields.Datetime.now()
        date_str = dt.strftime('%Y%m%d')
        if weight_g is not None:
            return f"{sku}-{int(weight_g)}G-{date_str}-{int(seq):04d}"
        return f"{sku}-{date_str}-{int(seq):04d}"

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
        """Populate finished/byproduct move lines in *units*.

        Odoo's `mrp.production.button_mark_done()` processes only moves linked
        to the production (move_finished_ids / move_byproduct_ids). Earlier
        versions created standalone `stock.move` records that were not always
        picked up by the standard workflow, so no inventory/cost was generated.

        This method:
        - Writes lot-tracked move lines for the main finished product.
        - Creates/updates byproduct (waste) moves if needed (cost_share=0).
        - Stores the entered weight (g) on the lot via `x_cw_weight_g` if that
          custom field exists.
        """
        self.ensure_one()
        prod = self.production_id
        if not prod:
            return

        finished_product = prod.product_id
        unit_uom = finished_product.uom_id

        # --- Main finished move (good pieces)
        good_lines = self.line_ids.filtered(lambda l: not l.is_waste and l.qty_units)
        total_good_units = sum(good_lines.mapped('qty_units'))

        main_move = prod.move_finished_ids.filtered(lambda m: m.product_id == finished_product)[:1]
        if not main_move:
            # Fallback: create a move linked to the production.
            main_move = self.env['stock.move'].create({
                'name': finished_product.display_name,
                'product_id': finished_product.id,
                'product_uom': unit_uom.id,
                'product_uom_qty': total_good_units,
                'location_id': prod.location_src_id.id,
                'location_dest_id': prod.location_dest_id.id,
                'company_id': prod.company_id.id,
                'production_id': prod.id,
                'picking_type_id': prod.picking_type_id.id,
            })
        else:
            # Ensure expected qty equals what we will produce.
            main_move.product_uom_qty = total_good_units
            if main_move.product_uom != unit_uom:
                main_move.product_uom = unit_uom

        # Reset any existing done lines so we don't double-produce.
        main_move.move_line_ids.unlink()

        seq = 1
        for line in good_lines:
            units = int(line.qty_units or 0)
            if units <= 0:
                continue
            # If pieces are identical and product is not tracked by serial, allow a single lot with qty>1
            if finished_product.tracking != 'serial' and units > 1:
                lot = self.env['stock.lot'].create({
                    'name': self._make_lot_name(finished_product, self.production_date, seq, weight_g=line.weight_g),
                    'product_id': finished_product.id,
                    'company_id': prod.company_id.id,
                })
                if 'x_cw_weight_g' in lot._fields:
                    lot.x_cw_weight_g = int(line.weight_g or 0)
                ml_vals = {
                    'move_id': main_move.id,
                    'product_id': finished_product.id,
                    'product_uom_id': finished_uom.id,
                    'qty_done': units,
                    'location_id': main_move.location_id.id,
                    'location_dest_id': main_move.location_dest_id.id,
                    'company_id': prod.company_id.id,
                }
                if finished_product.tracking != 'none':
                    ml_vals['lot_id'] = lot.id
                main_move_line_vals_list.append(ml_vals)
                seq += 1
                continue

            # Serial-tracked (or qty=1): one lot per unit
            for _ in range(units):
                lot = self.env['stock.lot'].create({
                    'name': self._make_lot_name(finished_product, self.production_date, seq, weight_g=line.weight_g),
                    'product_id': finished_product.id,
                    'company_id': prod.company_id.id,
                })
                if 'x_cw_weight_g' in lot._fields:
                    lot.x_cw_weight_g = int(line.weight_g or 0)
                ml_vals = {
                    'move_id': main_move.id,
                    'product_id': finished_product.id,
                    'product_uom_id': finished_uom.id,
                    'qty_done': 1.0,
                    'location_id': main_move.location_id.id,
                    'location_dest_id': main_move.location_dest_id.id,
                    'company_id': prod.company_id.id,
                }
                if finished_product.tracking != 'none':
                    ml_vals['lot_id'] = lot.id
                main_move_line_vals_list.append(ml_vals)
                seq += 1
        # --- Waste / byproduct move (optional)
        waste_lines = self.line_ids.filtered(lambda l: l.is_waste and l.qty_units)
        if waste_lines and self.waste_product_id:
            waste_product = self.waste_product_id
            waste_uom = waste_product.uom_id
            total_waste_units = sum(waste_lines.mapped('qty_units'))

            waste_move = prod.move_byproduct_ids.filtered(lambda m: m.product_id == waste_product)[:1]
            if not waste_move:
                vals = {
                    'name': waste_product.display_name,
                    'product_id': waste_product.id,
                    'product_uom': waste_uom.id,
                    'product_uom_qty': total_waste_units,
                    'location_id': prod.location_src_id.id,
                    'location_dest_id': prod.location_dest_id.id,
                    'company_id': prod.company_id.id,
                    'production_id': prod.id,
                    'picking_type_id': prod.picking_type_id.id,
                }
                # cost_share is the supported knob to exclude byproducts from cost allocation
                if 'cost_share' in self.env['stock.move']._fields:
                    vals['cost_share'] = 0.0
                waste_move = self.env['stock.move'].create(vals)
            else:
                waste_move.product_uom_qty = total_waste_units
                if waste_move.product_uom != waste_uom:
                    waste_move.product_uom = waste_uom
                if 'cost_share' in waste_move._fields:
                    total_good_w = sum((l.weight_g or 0.0) * (l.qty_units or 0.0) for l in good_lines)
                    total_waste_w = sum((l.weight_g or 0.0) * (l.qty_units or 0.0) for l in waste_lines)
                    total_w = total_good_w + total_waste_w
                    waste_move.cost_share = (total_waste_w / total_w * 100.0) if total_w else 0.0

            waste_move.move_line_ids.unlink()
            for line in waste_lines:
                lot = self.env['stock.lot'].create({
                    'name': self._make_lot_name(waste_product, self.production_date, seq, weight_g=line.weight_g),
                    'product_id': waste_product.id,
                    'company_id': prod.company_id.id,
                })
                if 'x_cw_weight_g' in lot._fields:
                    lot.x_cw_weight_g = int(line.weight_g or 0)

                self.env['stock.move.line'].create({
                    'move_id': waste_move.id,
                    'product_id': waste_product.id,
                    'product_uom_id': waste_uom.id,
                    'qty_done': line.qty_units,
                    'lot_id': lot.id,
                    'location_id': waste_move.location_id.id,
                    'location_dest_id': waste_move.location_dest_id.id,
                    'company_id': prod.company_id.id,
                })
                seq += 1

        # Keep a reference to consumed value for future costing logic
        self.cw_consumed_value = consumed_value


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

        # Cerrar OF (evitar loop y saltar wizard)
        ctx = dict(self.env.context, cw_from_wizard=True)
        prod = prod.with_context(ctx)
        prod.write({"date_finished": self.production_date})
        prod.button_mark_done()
        return {"type": "ir.actions.act_window_close"}
