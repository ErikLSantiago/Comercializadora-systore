from ast import literal_eval

from odoo import fields, models
from odoo.tools.float_utils import float_compare, float_is_zero


class StockMove(models.Model):
    _inherit = 'stock.move'

    surplus_transfer_lot_id = fields.Many2one(
        'stock.lot',
        string='Lote de Surplus',
        copy=False,
        readonly=True,
        check_company=True,
        help=(
            'En una transferencia generada por una regla Surplus, limita la reserva '
            'al lote/serie que realmente quedó libre en la operación origen.'
        ),
    )
    surplus_processed = fields.Boolean(
        string='Surplus procesado',
        default=False,
        copy=False,
        readonly=True,
        index=True,
        help=(
            'Indica que la llegada representada por este movimiento ya fue evaluada '
            'por una regla Surplus. Evita volver a transferirla después.'
        ),
    )

    def _surplus_rule_for_arrival(self):
        """Return the applicable Surplus rule for this arrival, if any."""
        self.ensure_one()
        if (
            self.surplus_processed
            or not self.product_id
            or not self.product_id.is_storable
            or self.is_inventory
            or self.origin_returned_move_id
            or not self.location_dest_id
        ):
            return self.env['stock.rule']

        warehouse = (
            self.warehouse_id
            or self.picking_id.picking_type_id.warehouse_id
            or self.location_dest_id.warehouse_id
        )
        values = {
            'route_ids': self.route_ids,
            'product_packaging_id': self.product_packaging_id,
            'warehouse_id': warehouse,
        }
        procurement_group = self.env['procurement.group']
        rule = procurement_group._get_surplus_rule(
            self.product_id,
            self.location_dest_id,
            values,
        )

        excluded_rule_ids = []
        while rule and rule.push_domain:
            if self.filtered_domain(literal_eval(rule.push_domain)):
                break
            excluded_rule_ids.append(rule.id)
            rule = procurement_group._get_surplus_rule(
                self.product_id,
                self.location_dest_id,
                {
                    **values,
                    'domain': [('id', 'not in', excluded_rule_ids)],
                },
            )
        return rule

    def _prepare_move_split_vals(self, qty):
        vals = super()._prepare_move_split_vals(qty)
        if self.picking_id.is_surplus_auto_transfer and self.surplus_transfer_lot_id:
            vals['surplus_transfer_lot_id'] = self.surplus_transfer_lot_id.id
        return vals

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
        """Keep generated Surplus transfers on the exact received lot/serial.

        Wholesale Allocation can keep filtering sale reservations by associated
        PO lots. This hook only affects moves created by Surplus and therefore
        composes cleanly with that module through the normal ``super()`` chain.
        """
        self.ensure_one()
        target_lot = self.surplus_transfer_lot_id
        picking = self.picking_id

        if not (
            picking
            and picking.is_surplus_auto_transfer
            and target_lot
            and self.product_id.tracking != 'none'
        ):
            return super()._update_reserved_quantity(
                quantity,
                location_id,
                lot_id=lot_id,
                package_id=package_id,
                owner_id=owner_id,
                strict=strict,
                **kwargs
            )

        if lot_id and lot_id != target_lot:
            return 0

        # A strict call already points to one exact quant combination.
        if strict:
            return super()._update_reserved_quantity(
                quantity,
                location_id,
                lot_id=target_lot,
                package_id=package_id,
                owner_id=owner_id,
                strict=True,
                **kwargs
            )

        # With strict=False Odoo may gather child locations. Iterate only quants
        # of the target lot and reserve each exact combination strictly. This
        # avoids falling back to unrelated lots if concurrency reduces stock.
        rounding = self.product_id.uom_id.rounding
        remaining = quantity
        taken = 0.0
        quants = self.env['stock.quant'].sudo().search([
            ('product_id', '=', self.product_id.id),
            ('location_id', 'child_of', location_id.id),
            ('lot_id', '=', target_lot.id),
            ('quantity', '>', 0),
        ], order='in_date, id')

        for quant in quants:
            if float_is_zero(remaining, precision_rounding=rounding):
                break
            available = quant.quantity - quant.reserved_quantity
            if float_compare(available, 0.0, precision_rounding=rounding) <= 0:
                continue
            wanted = min(remaining, available)
            reserved = super()._update_reserved_quantity(
                wanted,
                quant.location_id,
                lot_id=target_lot,
                package_id=quant.package_id or None,
                owner_id=quant.owner_id or None,
                strict=True,
                **kwargs
            )
            taken += reserved
            remaining -= reserved
            if float_compare(remaining, 0.0, precision_rounding=rounding) <= 0:
                break
        return taken
