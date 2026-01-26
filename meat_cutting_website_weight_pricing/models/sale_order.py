# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    mc_web_reserved_until = fields.Datetime(
        string="Reserva web hasta",
        readonly=True,
        copy=False,
    )

    def _mc_get_reservation_minutes(self):
        """Reservation window in minutes."""
        return 8

    def _mc_web_get_source_location(self):
        """Return the internal stock location used as source for website selection."""
        self.ensure_one()
        if self.warehouse_id and self.warehouse_id.lot_stock_id:
            return self.warehouse_id.lot_stock_id

        wh = self.env['stock.warehouse'].search([
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if wh and wh.lot_stock_id:
            return wh.lot_stock_id

        return self.env.ref('stock.stock_location_stock')

    def _mc_available_lots_fefo(self, product, location, qty_pieces):
        """Pick lots for a product in FEFO order.

        Returns a python list of stock.lot records. It may contain duplicates when a lot has
        quantity > 1 and is used multiple times.
        """
        self.ensure_one()

        qty_pieces = int(qty_pieces or 0)
        if qty_pieces <= 0:
            return []

        StockQuant = self.env['stock.quant']
        quants = StockQuant.search([
            ('product_id', '=', product.id),
            ('location_id', 'child_of', location.id),
            ('quantity', '>', 0),
            ('lot_id', '!=', False),
        ])

        def _exp_date(lot):
            # Some databases use different field names. Prefer expiration_date, fallback to use_expiration_date.
            return getattr(lot, 'expiration_date', False) or getattr(lot, 'use_expiration_date', False) or False

        def _sort_key(q):
            lot = q.lot_id
            exp = _exp_date(lot) or fields.Datetime.to_datetime('9999-12-31 00:00:00')
            created = lot.create_date or fields.Datetime.to_datetime('9999-12-31 00:00:00')
            return (exp, created, q.id)

        quants = sorted(quants, key=_sort_key)

        chosen = []
        remaining = qty_pieces
        for q in quants:
            if remaining <= 0:
                break
            if not q.lot_id:
                continue

            # In this flow, we assume 1 piece = 1 unit in stock. If quantity is >1, we can reuse the same lot.
            available_pieces = int(q.quantity)
            while available_pieces > 0 and remaining > 0:
                chosen.append(q.lot_id)
                available_pieces -= 1
                remaining -= 1

        return chosen

    def mc_web_reserve_and_recompute(self):
        """At checkout, select lots and recompute line price from the real weights.

        For now we only recompute + store the chosen lots for display; the hard reservation will be
        reinforced later.
        """
        for order in self:
            location = order._mc_web_get_source_location()

            for line in order.order_line:
                tmpl = line.product_id.product_tmpl_id
                if not getattr(tmpl, 'x_use_weight_sale_price', False):
                    continue

                qty_pieces = int(line.product_uom_qty or 0)
                if qty_pieces <= 0:
                    continue

                lot_list = order._mc_available_lots_fefo(line.product_id, location, qty_pieces)

                # Store chosen lots (unique) just for UI/traceability.
                if hasattr(line, 'x_web_reserved_lot_ids'):
                    line.x_web_reserved_lot_ids = [(6, 0, list({l.id for l in lot_list}))]

                # Recompute price and update line description.
                if hasattr(line, 'mc_web_compute_price_from_lots'):
                    line.mc_web_compute_price_from_lots(lot_list)

            # Optional timestamp (useful later for reservation expiry).
            order.mc_web_reserved_until = fields.Datetime.now() + timedelta(minutes=order._mc_get_reservation_minutes())

        return True
