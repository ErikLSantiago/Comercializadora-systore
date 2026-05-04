from odoo import models
from odoo.tools.float_utils import float_compare, float_is_zero


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _wholesale_allocation_allowed_lots(self):
        """Return allowed stock.lot records for this move.

        In this module the lot name must match the associated purchase order
        number on the originating sale order.
        """
        self.ensure_one()
        picking = self.picking_id
        if not picking or not picking.is_wholesale_allocation:
            return self.env['stock.lot']
        allowed_names = picking.associated_purchase_order_ids.mapped('name')
        if not allowed_names:
            return self.env['stock.lot']
        return self.env['stock.lot'].search([
            ('name', 'in', allowed_names),
            ('product_id', '=', self.product_id.id),
        ])

    def _wholesale_allocation_should_filter_auto_reservation(self):
        self.ensure_one()
        picking = self.picking_id
        return bool(
            picking
            and picking.is_wholesale_allocation
            and picking.associated_purchase_order_ids
            and self.product_id.tracking != 'none'
        )

    def _update_reserved_quantity(
        self,
        quantity,
        location_id,
        lot_id=None,
        package_id=None,
        owner_id=None,
        strict=True,
        **kwargs
    ):
        """
        Odoo 18 compatible hook.

        Phase 1 rule:
        - automatic reservation for wholesale pickings may reserve only lots
          whose names match the associated purchase order names;
        - if Odoo calls this method without lot_id, we reserve manually by
          iterating only over the allowed lots. This avoids Odoo falling back
          to FIFO/oldest stock from unrelated lots;
        - users may still add external lots manually on move lines.
        """
        self.ensure_one()

        if not self._wholesale_allocation_should_filter_auto_reservation():
            return super()._update_reserved_quantity(
                quantity,
                location_id,
                lot_id=lot_id,
                package_id=package_id,
                owner_id=owner_id,
                strict=strict,
                **kwargs
            )

        allowed_lots = self._wholesale_allocation_allowed_lots()
        if not allowed_lots:
            return 0

        # If Odoo already chose a lot, block it unless it is allowed.
        if lot_id:
            if lot_id not in allowed_lots:
                return 0
            return super()._update_reserved_quantity(
                quantity,
                location_id,
                lot_id=lot_id,
                package_id=package_id,
                owner_id=owner_id,
                strict=strict,
                **kwargs
            )

        # Odoo's normal assign flow can call this method without lot_id. If we
        # delegate that call to super(), Odoo may reserve any available lot. So
        # for wholesale moves we reserve by trying only the allowed lots.
        rounding = self.product_id.uom_id.rounding
        remaining_qty = quantity
        taken_qty = 0
        for allowed_lot in allowed_lots:
            if float_is_zero(remaining_qty, precision_rounding=rounding):
                break
            reserved = super()._update_reserved_quantity(
                remaining_qty,
                location_id,
                lot_id=allowed_lot,
                package_id=package_id,
                owner_id=owner_id,
                strict=strict,
                **kwargs
            )
            taken_qty += reserved
            remaining_qty -= reserved
            if float_compare(remaining_qty, 0, precision_rounding=rounding) <= 0:
                break
        return taken_qty
