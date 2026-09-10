# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        """Before validating vendor receipts, assign lot/serial using origin.

        Important: this module must never complete the demanded quantity by itself.
        It only assigns tracking to quantities that the user already counted in the
        detailed operation lines, using stock.move.line.quantity on Odoo 18.
        """
        self._auto_assign_tracking_from_origin()
        return super().button_validate()

    def _auto_assign_tracking_from_origin(self):
        """Assign lot/serial numbers from picking.origin for vendor receipts only.

        Scope:
        - Only receipts whose source location is a vendor/supplier location.
        - Also accepts source location complete name 'Partners/Vendors'.
        - Only products with tracking = lot or serial.
        - Uses the counted/done quantity on stock.move.line, not demand.
        - Does not create move lines from product_uom_qty.
        - Does not overwrite an existing lot_id or lot_name.
        """
        for picking in self:
            if not picking._should_auto_assign_tracking_from_origin():
                continue

            lot_name = (picking.origin or "").strip()
            if not lot_name:
                raise UserError(_(
                    "The transfer %s comes from a vendor location but has no Origin. "
                    "The Origin is required to create/assign the lot or serial number."
                ) % (picking.name,))

            picking._assign_tracking_to_counted_move_lines(lot_name)

    def _should_auto_assign_tracking_from_origin(self):
        self.ensure_one()
        location = self.location_id
        return bool(
            location
            and (
                location.usage == "supplier"
                or location.complete_name == "Partners/Vendors"
                or location.display_name == "Partners/Vendors"
            )
        )

    def _assign_tracking_to_counted_move_lines(self, base_lot_name):
        """Assign lots only to move lines with counted/done quantity.

        The previous version created detailed operation lines based on demand
        (product_uom_qty). That caused Odoo to validate the full ordered quantity
        even when the user only counted a partial receipt. This method intentionally
        skips lines with quantity = 0 and never creates lines from demand.
        """
        self.ensure_one()
        StockLot = self.env["stock.lot"]

        for line in self.move_line_ids.filtered(lambda ml: ml.product_id.tracking != "none"):
            if line.lot_id or getattr(line, "lot_name", False):
                continue

            counted_qty = self._get_counted_qty(line)
            if float_is_zero(counted_qty, precision_rounding=line.product_uom_id.rounding):
                continue

            lot = StockLot.search([
                ("name", "=", base_lot_name),
                ("product_id", "=", line.product_id.id),
                "|",
                ("company_id", "=", self.company_id.id),
                ("company_id", "=", False),
            ], limit=1)
            if not lot:
                lot = StockLot.create({
                    "name": base_lot_name,
                    "product_id": line.product_id.id,
                    "company_id": self.company_id.id,
                })

            line.lot_id = lot.id

    def _get_counted_qty(self, line):
        """Odoo 17/18 compatibility: qty_done was renamed to quantity."""
        if "quantity" in line._fields:
            return line.quantity
        return line.qty_done
