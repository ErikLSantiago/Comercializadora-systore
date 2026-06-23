from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    systore_upc_picking_validated = fields.Boolean(
        string='UPC/EAN validado en recolección',
        copy=False,
        readonly=True,
    )
    systore_require_tracking_on_pack = fields.Boolean(
        string='Exigir guía en empaque',
        related='picking_type_id.systore_require_tracking_on_pack',
        readonly=True,
    )
    systore_batch_readiness_state = fields.Selection(
        selection=[
            ('complete', 'Completa'),
            ('partial', 'Parcial'),
        ],
        string='Estado para lote',
        compute='_compute_systore_batch_readiness_state',
        store=True,
        readonly=True,
        help='Indica si la operación está completa o parcial comparando Demanda contra Cantidad lista/reservada. Se usa para excluir parciales de Batch Picking.',
    )

    @api.depends('state', 'move_ids_without_package.product_uom_qty', 'move_ids_without_package.quantity', 'move_ids_without_package.state', 'move_ids_without_package.move_line_ids.quantity', 'move_ids_without_package.move_line_ids.state')
    def _compute_systore_batch_readiness_state(self):
        for picking in self:
            if picking.state in ('done', 'cancel'):
                picking.systore_batch_readiness_state = 'complete'
                continue
            demand, ready = picking._systore_batch_demand_ready_qty()
            if float_is_zero(demand, precision_rounding=0.00001):
                picking.systore_batch_readiness_state = 'complete'
            elif float_compare(ready, demand, precision_rounding=0.00001) < 0:
                picking.systore_batch_readiness_state = 'partial'
            else:
                picking.systore_batch_readiness_state = 'complete'

    def write(self, vals):
        # Cuando se agregan traslados a un Batch Picking, permite excluir automáticamente
        # las órdenes parciales sin bloquear la asignación del resto.
        if vals.get('batch_id') and not self.env.context.get('systore_skip_partial_batch_filter'):
            to_skip = self.filtered(lambda p: p._systore_should_exclude_from_batch())
            to_write = self - to_skip
            result = True
            if to_write:
                result = super(StockPicking, to_write.with_context(systore_skip_partial_batch_filter=True)).write(vals)
            if to_skip:
                batch = self.env['stock.picking.batch'].browse(vals.get('batch_id'))
                if batch.exists() and hasattr(batch, 'message_post'):
                    names = ', '.join(to_skip.mapped('name'))
                    batch.message_post(body=_(
                        'Se excluyeron las siguientes recolecciones del Batch Picking porque tienen productos parcialmente disponibles: %s'
                    ) % names)
            return result
        return super().write(vals)

    def button_validate(self):
        # Recepción: primero conserva el flujo de registro UPC/EAN.
        # Recolección/Empaque: el wizard de UPC/EAN también puede capturar la guía,
        # por eso debe abrirse antes que el wizard independiente de guía.
        if self.env.context.get('systore_skip_upc_receipt_wizard'):
            result = super().button_validate()
            self._systore_propagate_pack_tracking_to_outgoing()
            return result

        pickings_to_check = self.filtered(lambda p: p._systore_needs_upc_receipt_wizard())
        if pickings_to_check:
            picking = pickings_to_check[0]
            wizard = self.env['stock.receipt.upc.wizard'].create_from_picking(picking)
            return {
                'name': _('Registrar UPC/EAN de recepción'),
                'type': 'ir.actions.act_window',
                'res_model': 'stock.receipt.upc.wizard',
                'view_mode': 'form',
                'target': 'new',
                'res_id': wizard.id,
            }

        if not self.env.context.get('systore_skip_upc_picking_wizard'):
            pickings_to_validate = self.filtered(lambda p: p._systore_needs_upc_picking_wizard())
            if pickings_to_validate:
                picking = pickings_to_validate[0]
                wizard = self.env['stock.picking.upc.wizard'].create_from_picking(picking)
                return {
                    'name': _('Validar UPC/EAN de recolección'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'stock.picking.upc.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'res_id': wizard.id,
                }

        # Si un tipo de operación de empaque no exige UPC/EAN pero sí guía,
        # se conserva el wizard simple de guía como respaldo.
        if not self.env.context.get('systore_skip_pack_tracking_wizard'):
            tracking_pickings = self.filtered(lambda p: p._systore_needs_pack_tracking_wizard())
            if tracking_pickings:
                picking = tracking_pickings[0]
                wizard = self.env['stock.pack.tracking.wizard'].create({'picking_id': picking.id})
                return {
                    'name': _('Capturar número de guía'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'stock.pack.tracking.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'res_id': wizard.id,
                }

        result = super().button_validate()
        self._systore_propagate_pack_tracking_to_outgoing()
        return result

    def _systore_warehouse_is_allowed(self, field_name):
        self.ensure_one()
        warehouse = self.picking_type_id.warehouse_id
        if not warehouse:
            return False
        allowed_warehouses = getattr(self.company_id, field_name)
        return warehouse in allowed_warehouses

    def _systore_upc_receipt_enabled_for_warehouse(self):
        return self._systore_warehouse_is_allowed('systore_upc_receipt_warehouse_ids')

    def _systore_upc_validation_enabled_for_warehouse(self):
        return self._systore_warehouse_is_allowed('systore_upc_validation_warehouse_ids')

    def _systore_needs_upc_receipt_wizard(self):
        self.ensure_one()
        if self.picking_type_id.code != 'incoming':
            return False
        if not self._systore_upc_receipt_enabled_for_warehouse():
            return False
        if not self.picking_type_id.systore_require_upc_on_receipt:
            return False
        if self.state in ('done', 'cancel'):
            return False
        products = self._systore_receipt_products_to_validate()
        return bool(products)

    def _systore_receipt_products_to_validate(self):
        self.ensure_one()
        products = self.env['product.product']
        for move in self.move_ids_without_package.filtered(lambda m: m.state not in ('done', 'cancel')):
            if move.product_id and move.product_id.type in ('product', 'consu'):
                products |= move.product_id
        return products

    def _systore_receipt_validation_groups(self):
        """Return receipt wizard rows grouped by product with demand and current qty."""
        self.ensure_one()
        groups = {}
        order = []
        moves = self.move_ids_without_package.filtered(
            lambda m: m.state not in ('done', 'cancel')
            and m.product_id
            and m.product_id.type in ('product', 'consu')
        )
        for move in moves.sorted(key=lambda m: (getattr(m, 'sequence', 0) or 0, m.id)):
            key = move.product_id.id
            if key not in groups:
                groups[key] = {
                    'product_id': move.product_id.id,
                    'demand_qty': 0.0,
                    'quantity': 0.0,
                }
                order.append(key)
            groups[key]['demand_qty'] += move.product_uom_qty or 0.0
            current_qty = self._systore_move_effective_qty(move)
            groups[key]['quantity'] += current_qty or 0.0

        for key in order:
            if float_is_zero(groups[key]['quantity'], precision_rounding=self.env['product.product'].browse(key).uom_id.rounding):
                groups[key]['quantity'] = groups[key]['demand_qty']

        return [groups[key] for key in order]

    def _systore_needs_upc_picking_wizard(self):
        self.ensure_one()
        if self.picking_type_id.code == 'incoming':
            return False
        if not self._systore_upc_validation_enabled_for_warehouse():
            return False
        if not self.picking_type_id.systore_require_upc_on_picking:
            return False
        if self.systore_upc_picking_validated:
            return False
        if self.state in ('done', 'cancel'):
            return False
        return bool(self._systore_picking_products_to_validate())

    def _systore_picking_products_to_validate(self):
        self.ensure_one()
        products = self.env['product.product']
        for move in self.move_ids_without_package.filtered(lambda m: m.state not in ('done', 'cancel')):
            if not move.product_id or move.product_id.type not in ('product', 'consu'):
                continue
            qty = self._systore_move_effective_qty(move)
            if float_is_zero(qty, precision_rounding=move.product_uom.rounding):
                continue
            products |= move.product_id
        return products

    def _systore_move_effective_qty(self, move):
        """Return the quantity that is being advanced/validated in a version-safe way."""
        qty = 0.0
        for ml in move.move_line_ids:
            if 'quantity' in ml._fields:
                qty += ml.quantity or 0.0
            elif 'qty_done' in ml._fields:
                qty += ml.qty_done or 0.0
        if not qty:
            if 'quantity' in move._fields:
                qty = move.quantity or 0.0
            elif 'quantity_done' in move._fields:
                qty = move.quantity_done or 0.0
            elif 'qty_done' in move._fields:
                qty = move.qty_done or 0.0
        if not qty:
            qty = move.product_uom_qty or 0.0
        return qty


    def _systore_pick_validation_groups(self):
        """Return validation rows for PICK grouped only by product.

        Important: this intentionally ignores stock.lot. In this flow the operator
        validates the product/UPC for the total demand of the product, even when
        Odoo reserved that product from several native lots.
        """
        self.ensure_one()
        groups = {}
        order = []

        moves = self.move_ids_without_package.filtered(
            lambda m: m.state not in ('done', 'cancel')
            and m.product_id
            and m.product_id.type in ('product', 'consu')
        )
        for move in moves.sorted(key=lambda m: (getattr(m, 'sequence', 0) or 0, m.id)):
            qty = self._systore_move_effective_qty(move)
            if float_is_zero(qty, precision_rounding=move.product_uom.rounding):
                qty = move.product_uom_qty or 0.0
            if float_is_zero(qty, precision_rounding=move.product_uom.rounding):
                continue
            key = move.product_id.id
            if key not in groups:
                groups[key] = {
                    'product_id': move.product_id.id,
                    'lot_id': False,
                    'demand_qty': 0.0,
                }
                order.append(key)
            groups[key]['demand_qty'] += qty

        return [groups[key] for key in order]



    def _systore_should_exclude_from_batch(self):
        """Return True when this picking should not be assigned to a Batch Picking.

        Business rule: with the company option enabled, exclude a picking when the
        operation is marked as Parcial. This intentionally does not depend on the
        UPC warehouse configuration, so the Batch filter can be used as an
        operational rule from the transfer status itself.
        """
        self.ensure_one()
        if not self.company_id.systore_exclude_partial_pickings_from_batch:
            return False
        if self.state in ('done', 'cancel'):
            return False
        return self.systore_batch_readiness_state == 'partial'

    def _systore_batch_demand_ready_qty(self):
        """Return total demand and ready qty for Batch Picking eligibility.

        The UI shows the same idea as Demanda vs Cantidad. We intentionally check
        the whole picking, not only a single move, because a sales order with one
        ready line and another waiting line must be excluded entirely.
        """
        self.ensure_one()
        demand = 0.0
        ready = 0.0
        moves = self.move_ids_without_package.filtered(
            lambda m: m.state not in ('done', 'cancel')
            and m.product_id
            and m.product_id.type in ('product', 'consu')
        )
        for move in moves:
            move_demand = move.product_uom_qty or 0.0
            if float_is_zero(move_demand, precision_rounding=move.product_uom.rounding):
                continue
            demand += move_demand
            ready += min(self._systore_move_ready_qty_for_batch(move), move_demand)
        return demand, ready

    def _systore_move_ready_qty_for_batch(self, move):
        """Return quantity that is actually ready/reserved for the move.

        Prefer move lines because they reflect what is visible as ready quantity
        in detailed operations. If a line is still waiting, it usually has no
        usable move line quantity. Fallbacks are kept for Odoo/custom flows.
        """
        qty = 0.0
        for ml in move.move_line_ids:
            if ml.state in ('done', 'cancel'):
                continue
            if 'quantity' in ml._fields:
                qty += ml.quantity or 0.0
            elif 'reserved_uom_qty' in ml._fields:
                qty += ml.reserved_uom_qty or 0.0
            elif 'reserved_quantity' in ml._fields:
                qty += ml.reserved_quantity or 0.0
            elif 'product_uom_qty' in ml._fields:
                qty += ml.product_uom_qty or 0.0

        if qty:
            return qty

        # Odoo 18 stock.move.quantity is commonly the ready/done quantity shown
        # in operations. Some customizations only expose reserved_availability.
        if 'quantity' in move._fields:
            return move.quantity or 0.0
        if 'reserved_availability' in move._fields:
            return move.reserved_availability or 0.0
        if 'availability' in move._fields:
            return move.availability or 0.0
        return 0.0

    def _systore_needs_pack_tracking_wizard(self):
        self.ensure_one()
        if self.state in ('done', 'cancel'):
            return False
        if not self._systore_upc_validation_enabled_for_warehouse():
            return False
        if not self.picking_type_id.systore_require_tracking_on_pack:
            return False
        return not bool((self.carrier_tracking_ref or '').strip())

    def _systore_propagate_pack_tracking_to_outgoing(self):
        for picking in self:
            tracking = (picking.carrier_tracking_ref or '').strip()
            if not tracking or not picking.picking_type_id.systore_require_tracking_on_pack:
                continue

            next_pickings = picking.move_ids.move_dest_ids.mapped('picking_id').filtered(
                lambda p: p and p.id != picking.id and p.state not in ('done', 'cancel')
            )
            if not next_pickings:
                # Fallback for chained transfers where the destination picking is linked by group/origin.
                domain = [
                    ('id', '!=', picking.id),
                    ('state', 'not in', ('done', 'cancel')),
                    ('group_id', '=', picking.group_id.id if picking.group_id else False),
                    ('origin', '=', picking.origin or picking.name),
                ]
                next_pickings = self.search(domain)

            for next_picking in next_pickings:
                vals = {'carrier_tracking_ref': tracking}
                if next_picking.name and not next_picking.name.endswith('-%s' % tracking):
                    vals['name'] = '%s-%s' % (next_picking.name, tracking)
                next_picking.write(vals)
