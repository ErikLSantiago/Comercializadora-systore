    # -*- coding: utf-8 -*-
    from datetime import timedelta

    from odoo import _, api, fields, models
    from odoo.exceptions import UserError
    from odoo.tools.float_utils import float_is_zero

    class SaleOrder(models.Model):
        _inherit = "sale.order"

        mc_web_reservation_ids = fields.One2many("mc.web.reservation", "order_id", string="Reservas web", readonly=True)
        mc_web_reserved_until = fields.Datetime(string="Reserva web hasta", readonly=True, copy=False)

        def _mc_get_reservation_minutes(self):
            # 8 minutos por requerimiento
            return 8

        def _mc_get_reservation_location(self):
            """Ubicación para reservar: preferimos 'CED/Existencias' si existe.
            Si no, usamos la ubicación de stock principal de la compañía.
            """
            self.ensure_one()
            loc = self.env["stock.location"].search([("usage", "=", "internal"), ("complete_name", "ilike", "CED/Existencias")], limit=1)
            if loc:
                return loc
            wh = self.env["stock.warehouse"].search([("company_id", "=", self.company_id.id)], limit=1)
            if wh and wh.lot_stock_id:
                return wh.lot_stock_id
            # fallback: primera ubicación interna
            loc = self.env["stock.location"].search([("usage", "=", "internal")], limit=1)
            if not loc:
                raise UserError(_("No se encontró una ubicación interna para reservar existencias."))
            return loc

        def _mc_expiration_field_name(self):
            lot_model = self.env["stock.lot"]
            for fname in ["expiration_date", "use_date", "life_date", "removal_date"]:
                if fname in lot_model._fields:
                    return fname
            return None

        def _mc_available_lots_fefo(self, product, location, qty_needed):
            """Devuelve una lista de lotes disponibles ordenados por FEFO.
            Excluye lotes ya reservados (no expirados) por otros pedidos.
            """
            Quant = self.env["stock.quant"]
            now = fields.Datetime.now()

            # lotes reservados vigentes por otros pedidos
            reserved = self.env["mc.web.reservation"].search([
                ("product_id", "=", product.id),
                ("reserved_until", ">", now),
                ("order_id", "!=", self.id),
            ]).mapped("lot_id").ids

            domain = [
                ("product_id", "=", product.id),
                ("location_id", "child_of", location.id),
                ("quantity", ">", 0),
                ("lot_id", "!=", False),
            ]
            if reserved:
                domain.append(("lot_id", "not in", reserved))

            quants = Quant.search(domain)
            # consolidar por lote (1 pieza = 1 quant normalmente, pero por seguridad sumamos disponibilidad)
            lot_qty = {}
            for q in quants:
                lot = q.lot_id
                if not lot:
                    continue
                lot_qty.setdefault(lot.id, {"lot": lot, "qty": 0.0})
                lot_qty[lot.id]["qty"] += (q.quantity - q.reserved_quantity)

            candidates = [v for v in lot_qty.values() if v["qty"] > 0]
            exp_field = self._mc_expiration_field_name()

            def exp_dt(lot):
                if not exp_field:
                    return False
                return getattr(lot, exp_field)

            # FEFO: menor fecha primero; lotes sin fecha al final
            candidates.sort(key=lambda x: (exp_dt(x["lot"]) is False, exp_dt(x["lot"]) or fields.Datetime.from_string("2999-12-31 00:00:00"), x["lot"].id))

            chosen = []
            remaining = qty_needed
            for item in candidates:
                if remaining <= 0:
                    break
                take = int(min(item["qty"], remaining))
                if take <= 0:
                    continue
                # agregamos el lote 'take' veces (1 por pieza)
                chosen.extend([item["lot"]] * take)
                remaining -= take

            return chosen, remaining

        def mc_web_reserve_and_recompute(self):
            """Reserva lotes/series para líneas con precio por peso y recalcula precio_unit.
            Se ejecuta en checkout (antes de pago) para cobrar el valor exacto.
            """
            for so in self:
                so.ensure_one()
                now = fields.Datetime.now()

                # limpiar reservas expiradas del propio pedido
                so.mc_web_reservation_ids.filtered(lambda r: r.reserved_until and r.reserved_until <= now).unlink()

                # si ya tiene reserva vigente, la reutilizamos (pero recalculamos precios por si cambiaron reglas)
                minutes = so._mc_get_reservation_minutes()
                reserved_until = now + timedelta(minutes=minutes)
                location = so._mc_get_reservation_location()

                # validar líneas
                weight_lines = so.order_line.filtered(lambda l: l.product_id and l.product_id.product_tmpl_id.x_use_weight_sale_price)
                if not weight_lines:
                    return True

                # borrar reservas previas del pedido y volver a reservar (simple y seguro)
                so.mc_web_reservation_ids.unlink()

                uom_kg = self.env.ref("uom.product_uom_kgm", raise_if_not_found=False)
                if not uom_kg:
                    raise UserError(_("No se encontró la unidad de medida KG (uom.product_uom_kgm)."))

                for line in weight_lines:
                    qty = int(line.product_uom_qty or 0)
                    if qty <= 0:
                        continue

                    tmpl = line.product_id.product_tmpl_id
                    price_per_weight = tmpl.x_price_per_weight or 0.0
                    target_uom = tmpl.x_price_weight_uom_id or uom_kg

                    if float_is_zero(price_per_weight, precision_rounding=0.000001):
                        raise UserError(_("El producto %s no tiene 'Precio en peso' configurado.") % tmpl.display_name)

                    lots, remaining = so._mc_available_lots_fefo(line.product_id, location, qty)
                    if remaining > 0:
                        raise UserError(_(
                            "No hay suficientes piezas disponibles para %s.
"
                            "Requeridas: %s, disponibles: %s.
"
                            "Tip: Revisa existencias en %s."
                        ) % (line.product_id.display_name, qty, qty-remaining, location.complete_name))

                    # crear reservas y calcular peso
                    total_weight_kg = 0.0
                    for lot in lots:
                        w = getattr(lot, "x_weight_kg", 0.0) or 0.0
                        total_weight_kg += w
                        self.env["mc.web.reservation"].create({
                            "order_id": so.id,
                            "order_line_id": line.id,
                            "lot_id": lot.id,
                            "reserved_until": reserved_until,
                        })

                    # convertir kg -> uom objetivo
                    total_weight_in_uom = uom_kg._compute_quantity(total_weight_kg, target_uom)
                    price_total = total_weight_in_uom * price_per_weight
                    price_unit = price_total / qty

                    line.write({"price_unit": price_unit})

                so.write({"mc_web_reserved_until": reserved_until})
            return True

        @api.model
        def _mc_web_cron_release_expired(self):
            """Cron: libera reservas expiradas."""
            now = fields.Datetime.now()
            expired = self.env["mc.web.reservation"].search([("reserved_until", "<=", now)])
            # también limpiamos campo en la SO si ya no quedan reservas
            orders = expired.mapped("order_id")
            expired.unlink()
            for so in orders:
                if not so.mc_web_reservation_ids:
                    so.mc_web_reserved_until = False
            return True
