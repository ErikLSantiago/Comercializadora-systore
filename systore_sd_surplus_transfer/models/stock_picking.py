from collections import defaultdict
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare, float_is_zero, float_round


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_surplus_auto_transfer = fields.Boolean(
        string='Transferencia Surplus',
        default=False,
        copy=False,
        index=True,
        readonly=True,
    )
    surplus_rule_id = fields.Many2one(
        'stock.rule',
        string='Regla Surplus',
        copy=False,
        index=True,
        readonly=True,
        ondelete='set null',
    )
    # Technical name kept from 18.0.1.0.0 for a safe module upgrade.
    surplus_source_receipt_id = fields.Many2one(
        'stock.picking',
        string='Operación origen de Surplus',
        copy=False,
        index=True,
        readonly=True,
        ondelete='set null',
    )
    surplus_transfer_ids = fields.One2many(
        'stock.picking',
        'surplus_source_receipt_id',
        string='Transferencias Surplus',
        readonly=True,
    )
    surplus_transfer_count = fields.Integer(
        string='Transferencias Surplus',
        compute='_compute_surplus_transfer_count',
    )
    # Legacy field kept for upgrades; processing is now tracked on stock.move.
    surplus_transfer_processed = fields.Boolean(
        string='Excedente procesado (obsoleto)',
        default=False,
        copy=False,
        readonly=True,
    )

    @api.depends('surplus_transfer_ids')
    def _compute_surplus_transfer_count(self):
        for picking in self:
            picking.surplus_transfer_count = len(picking.surplus_transfer_ids)

    def action_view_surplus_transfers(self):
        self.ensure_one()
        transfers = self.surplus_transfer_ids
        action = {
            'name': _('Transferencias Surplus'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('id', 'in', transfers.ids)],
            'context': {'create': False},
        }
        if len(transfers) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': transfers.id,
            })
        return action

    def action_view_surplus_source_receipt(self):
        self.ensure_one()
        if not self.surplus_source_receipt_id:
            return False
        return {
            'name': _('Operación origen'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.surplus_source_receipt_id.id,
            'context': {'create': False},
        }

    def _create_backorder_picking(self):
        backorder = super()._create_backorder_picking()
        if self.is_surplus_auto_transfer:
            backorder.write({
                'is_surplus_auto_transfer': True,
                'surplus_source_receipt_id': self.surplus_source_receipt_id.id,
                'surplus_rule_id': self.surplus_rule_id.id,
            })
        return backorder

    # ---------------------------------------------------------------------
    # Quantity helpers
    # ---------------------------------------------------------------------

    def _surplus_free_quantity(self, product, location, lot=False):
        """Free stock below a location, optionally restricted to one lot."""
        domain = [
            ('product_id', '=', product.id),
            ('location_id', 'child_of', location.id),
        ]
        if product.tracking == 'none':
            domain.append(('lot_id', '=', False))
        else:
            if not lot:
                return 0.0
            domain.append(('lot_id', '=', lot.id))

        quants = self.env['stock.quant'].sudo().search(domain)
        available = sum(quants.mapped('quantity')) - sum(quants.mapped('reserved_quantity'))
        if float_compare(available, 0.0, precision_rounding=product.uom_id.rounding) <= 0:
            return 0.0
        return available

    def _surplus_resolve_lot(self, product, lot_name):
        self.ensure_one()
        if not lot_name:
            return self.env['stock.lot']
        return self.env['stock.lot'].search([
            ('product_id', '=', product.id),
            ('name', '=', lot_name),
            ('company_id', 'in', [False, self.company_id.id]),
        ], limit=1)

    @staticmethod
    def _surplus_lot_name(line):
        if line.product_id.tracking == 'none':
            return False
        return (line.lot_id.name or line.lot_name or '').strip() or False

    def _surplus_snapshot_before_done(self):
        """Capture free stock before this picking adds quantities to Surplus sources.

        Keys are ``(rule_id, product_id, lot_name)``. The snapshot is taken only
        for moves that have an applicable Surplus rule, allowing a single picking
        to feed different rules according to product/category/route applicability.
        """
        self.ensure_one()
        snapshot = {}
        move_rule_ids = {}

        candidate_moves = self.move_ids.filtered(
            lambda m: m.state not in ('done', 'cancel') and not m.surplus_processed
        )
        for move in candidate_moves:
            rule = move._surplus_rule_for_arrival()
            if not rule:
                continue
            move_rule_ids[move.id] = rule.id

            lines = move.move_line_ids.filtered(
                lambda ml: ml.product_id
                and ml.product_id.is_storable
                and float_compare(
                    ml.quantity,
                    0.0,
                    precision_rounding=ml.product_uom_id.rounding,
                ) > 0
                and ml.location_dest_id._child_of(rule.location_src_id)
            )

            # Normal stock operations have move lines. Keep an untracked fallback
            # for custom flows that set quantity on the move without explicit lines.
            if not lines and move.product_id.tracking == 'none' and float_compare(
                move.quantity,
                0.0,
                precision_rounding=move.product_uom.rounding,
            ) > 0:
                key = (rule.id, move.product_id.id, False)
                if key not in snapshot:
                    snapshot[key] = self._surplus_free_quantity(
                        move.product_id,
                        rule.location_src_id,
                    )
                continue

            for line in lines:
                lot_name = self._surplus_lot_name(line)
                key = (rule.id, line.product_id.id, lot_name)
                if key in snapshot:
                    continue
                lot = line.lot_id
                if line.product_id.tracking != 'none' and not lot:
                    lot = self._surplus_resolve_lot(line.product_id, lot_name)
                snapshot[key] = self._surplus_free_quantity(
                    line.product_id,
                    rule.location_src_id,
                    lot=lot,
                )

        return {
            'snapshot': snapshot,
            'move_rule_ids': move_rule_ids,
        }

    def _surplus_received_buckets(self, context_data):
        """Actual done quantities grouped by rule, product and lot."""
        self.ensure_one()
        move_rule_ids = context_data.get('move_rule_ids', {})
        buckets = defaultdict(lambda: {
            'rule': self.env['stock.rule'],
            'product': self.env['product.product'],
            'lot': self.env['stock.lot'],
            'received_qty': 0.0,
            'source_move_ids': set(),
        })

        for move_id, rule_id in move_rule_ids.items():
            move = self.env['stock.move'].browse(move_id).exists()
            rule = self.env['stock.rule'].browse(rule_id).exists()
            if not move or not rule or move.state != 'done':
                continue

            source_move_had_line = False
            for line in move.move_line_ids:
                if (
                    not line.product_id
                    or not line.product_id.is_storable
                    or not line.location_dest_id._child_of(rule.location_src_id)
                    or float_compare(
                        line.quantity,
                        0.0,
                        precision_rounding=line.product_uom_id.rounding,
                    ) <= 0
                ):
                    continue

                product = line.product_id
                lot = line.lot_id if product.tracking != 'none' else self.env['stock.lot']
                if product.tracking != 'none' and not lot:
                    # Never mix unidentified tracked stock into a Surplus transfer.
                    continue

                lot_name = lot.name if lot else False
                key = (rule.id, product.id, lot_name)
                qty = line.product_uom_id._compute_quantity(
                    line.quantity,
                    product.uom_id,
                    rounding_method='HALF-UP',
                )
                bucket = buckets[key]
                bucket['rule'] = rule
                bucket['product'] = product
                bucket['lot'] = lot
                bucket['received_qty'] += qty
                bucket['source_move_ids'].add(move.id)
                source_move_had_line = True

            if (
                not source_move_had_line
                and move.product_id.tracking == 'none'
                and float_compare(
                    move.quantity,
                    0.0,
                    precision_rounding=move.product_uom.rounding,
                ) > 0
            ):
                product = move.product_id
                qty = move.product_uom._compute_quantity(
                    move.quantity,
                    product.uom_id,
                    rounding_method='HALF-UP',
                )
                key = (rule.id, product.id, False)
                bucket = buckets[key]
                bucket['rule'] = rule
                bucket['product'] = product
                bucket['received_qty'] += qty
                bucket['source_move_ids'].add(move.id)

        return buckets

    # ---------------------------------------------------------------------
    # Existing demand gets first priority
    # ---------------------------------------------------------------------

    def _surplus_assign_origin_demand(self, rule, products):
        self.ensure_one()
        if not products:
            return

        candidate_moves = self.env['stock.move'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('product_id', 'in', products.ids),
            ('location_id', 'child_of', rule.location_src_id.id),
            ('state', 'in', ['confirmed', 'waiting', 'partially_available']),
            ('scrapped', '=', False),
            ('picking_id.is_surplus_auto_transfer', '=', False),
        ], order='reservation_date, priority desc, date asc, id asc')

        if candidate_moves:
            candidate_moves._action_assign()

    def _surplus_quantities_to_transfer(self, context_data):
        self.ensure_one()
        pre_snapshot = context_data.get('snapshot', {})
        buckets = self._surplus_received_buckets(context_data)

        products_by_rule = defaultdict(lambda: self.env['product.product'])
        for values in buckets.values():
            products_by_rule[values['rule'].id] |= values['product']

        # Odoo's standard validation already triggers assignments after incoming
        # and internal moves. Re-run specifically for each Surplus source so all
        # pending demand gets one final opportunity before the remainder is moved.
        for rule_id, products in products_by_rule.items():
            rule = self.env['stock.rule'].browse(rule_id)
            self._surplus_assign_origin_demand(rule, products)

        lines_by_rule = defaultdict(list)
        processed_move_ids = set()
        for key, values in buckets.items():
            rule = values['rule']
            product = values['product']
            lot = values['lot']
            received_qty = values['received_qty']
            processed_move_ids |= values['source_move_ids']
            rounding = product.uom_id.rounding

            post_free = self._surplus_free_quantity(
                product,
                rule.location_src_id,
                lot=lot,
            )
            pre_free = pre_snapshot.get(key, 0.0)
            free_from_arrival = max(post_free - pre_free, 0.0)
            qty = min(received_qty, free_from_arrival)
            qty = float_round(qty, precision_rounding=rounding, rounding_method='DOWN')

            if float_is_zero(qty, precision_rounding=rounding):
                continue

            lines_by_rule[rule.id].append({
                'product': product,
                'lot': lot,
                'qty': qty,
            })

        return lines_by_rule, processed_move_ids

    # ---------------------------------------------------------------------
    # Transfer creation from stock.rule configuration
    # ---------------------------------------------------------------------

    def _surplus_create_transfer(self, rule, transfer_lines):
        self.ensure_one()
        if not transfer_lines:
            return self.env['stock.picking']

        source_location = rule.location_src_id
        destination_location = rule.location_dest_id
        picking_type = rule.picking_type_id
        company = rule.company_id or self.company_id
        scheduled_date = fields.Datetime.now() + relativedelta(days=rule.delay or 0)

        if rule.group_propagation_option == 'fixed':
            group = rule.group_id
        elif rule.group_propagation_option == 'propagate':
            group = self.group_id
        else:
            group = self.env['procurement.group']

        transfer = self.env['stock.picking'].sudo().with_context(
            skip_surplus_auto_processing=True,
        ).create({
            'picking_type_id': picking_type.id,
            'location_id': source_location.id,
            'location_dest_id': destination_location.id,
            'company_id': company.id,
            'origin': _('Surplus de %s', self.name),
            'scheduled_date': scheduled_date,
            'group_id': group.id if group else False,
            'is_surplus_auto_transfer': True,
            'surplus_source_receipt_id': self.id,
            'surplus_rule_id': rule.id,
            'priority': self.priority,
        })

        move_vals = []
        for line in transfer_lines:
            product = line['product']
            lot = line['lot']
            move_vals.append({
                'name': product.display_name,
                'description_picking': product.display_name,
                'picking_id': transfer.id,
                'product_id': product.id,
                'product_uom_qty': line['qty'],
                'product_uom': product.uom_id.id,
                'location_id': source_location.id,
                'location_dest_id': destination_location.id,
                'company_id': company.id,
                'origin': self.name,
                'procure_method': 'make_to_stock',
                'rule_id': rule.id,
                'warehouse_id': (
                    rule.warehouse_id.id
                    or source_location.warehouse_id.id
                    or picking_type.warehouse_id.id
                    or False
                ),
                'date': scheduled_date,
                'propagate_cancel': rule.propagate_cancel,
                'priority': self.priority,
                'surplus_transfer_lot_id': lot.id if lot else False,
            })

        self.env['stock.move'].sudo().with_context(
            skip_surplus_auto_processing=True,
        ).create(move_vals)
        transfer.with_context(skip_surplus_auto_processing=True).action_confirm()
        transfer.with_context(skip_surplus_auto_processing=True).action_assign()
        transfer._surplus_trim_to_actual_reservation()
        return transfer

    def _surplus_trim_to_actual_reservation(self):
        """Do not leave Surplus demand waiting for stock from a later arrival."""
        for picking in self.filtered('is_surplus_auto_transfer'):
            active_moves = picking.move_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
            moves_to_cancel = self.env['stock.move']

            for move in active_moves:
                rounding = move.product_uom.rounding
                reserved_qty = move.quantity
                if float_is_zero(reserved_qty, precision_rounding=rounding):
                    moves_to_cancel |= move
                    continue
                if float_compare(
                    reserved_qty,
                    move.product_uom_qty,
                    precision_rounding=rounding,
                ) < 0:
                    move.product_uom_qty = reserved_qty

            if moves_to_cancel:
                moves_to_cancel._action_cancel()

            if not picking.move_ids.filtered(lambda m: m.state != 'cancel'):
                picking.action_cancel()

    def _surplus_process_after_done(self, context_data):
        self.ensure_one()
        lines_by_rule, processed_move_ids = self._surplus_quantities_to_transfer(context_data)

        for rule_id, transfer_lines in lines_by_rule.items():
            rule = self.env['stock.rule'].browse(rule_id).exists()
            if rule and rule.action == 'surplus':
                self._surplus_create_transfer(rule, transfer_lines)

        # Mark arrivals as evaluated even when no excess remained. This is
        # intentional: stock freed later must not be mistaken for this arrival.
        if processed_move_ids:
            self.env['stock.move'].browse(list(processed_move_ids)).write({
                'surplus_processed': True,
            })

    def _action_done(self):
        if self.env.context.get('skip_surplus_auto_processing'):
            return super()._action_done()

        snapshots = {}
        for picking in self:
            context_data = picking._surplus_snapshot_before_done()
            if context_data['move_rule_ids']:
                snapshots[picking.id] = context_data

        result = super()._action_done()

        for picking_id, context_data in snapshots.items():
            picking = self.browse(picking_id).exists()
            if picking and picking.state == 'done':
                picking._surplus_process_after_done(context_data)
        return result
