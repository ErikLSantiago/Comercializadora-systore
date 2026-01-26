# -*- coding: utf-8 -*-
from datetime import timedelta, datetime

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
    def _mc_available_lots_fefo(self, tmpl, location, qty_pieces):
        """Return a stock.lot recordset (serials) to use for the given qty_pieces.

        We pick FEFO (expiration_date asc, then create_date asc) and only lots with >0 qty in the
        given internal location.
        """
        self.ensure_one()
        if qty_pieces <= 0:
            return self.env['stock.lot']

        # Quants in the source location for this product
        Quant = self.env['stock.quant'].sudo()
        lots = self.env['stock.lot'].sudo().search([
            ('product_id', '=', tmpl.product_variant_id.id),
        ])

        # Build available lots list with their available qty in that location
        candidates = []
        for lot in lots:
            qty = sum(Quant.search([
                ('product_id', '=', tmpl.product_variant_id.id),
                ('location_id', 'child_of', location.id),
                ('lot_id', '=', lot.id),
            ]).mapped('quantity'))
            if qty > 0:
                candidates.append(lot)

        # Sort FEFO: expiration_date first (None at the end), then create_date
        def _fefo_key(l):
            exp = l.expiration_date or datetime.max
            return (exp, l.create_date or datetime.max, l.id)

        candidates.sort(key=_fefo_key)

        chosen = candidates[:qty_pieces]
        return self.env['stock.lot'].browse([l.id for l in chosen])


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
        """Web step: select FEFO lots and recompute the unit price.

        For now we **only** select lots and recompute price + show selected lot(s).
        Reservation will be hardened later (no quant reservation is performed here).
        """
        for order in self:
            location = order._mc_web_get_source_location()
            if not location:
                continue

            for line in order.order_line.filtered(lambda l: l.product_id and l.product_id.tracking in ('lot', 'serial')):
                tmpl = line.product_id.product_tmpl_id

                # Only apply to products using weight sale price logic (module 2)
                if not getattr(tmpl, 'x_use_weight_sale_price', False):
                    continue

                qty_pieces = int(line.product_uom_qty or 0)
                if qty_pieces <= 0:
                    continue

                lots = order._mc_available_lots_fefo(tmpl, location, qty_pieces)
                line.x_web_reserved_lot_ids = [(6, 0, lots.ids)]
                line.mc_web_compute_price_from_lots(lots)


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