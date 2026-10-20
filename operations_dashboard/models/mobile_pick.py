import hashlib
import json

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare

from .mobile_pick_policy import normalize_capture, group_pick_rows, allocate_pick_quantities
from odoo.osv.expression import AND


class MobilePickDashboard(models.AbstractModel):
    _inherit = 'systore.operations.dashboard'

    @api.model
    def open_mobile_pick(self, warehouse_id, selected_date=False, scope='date', picking_id=False, batch_id=False, readiness='complete'):
        warehouse = self._warehouse(warehouse_id)
        if readiness not in ('complete', 'partial'):
            raise ValidationError(_('Estado inválido.'))
        if warehouse.delivery_steps == 'pick_ship':
            return self.open_mobile_pack(warehouse_id, picking_id, batch_id, section='pick', readiness=readiness)
        self._parameters(selected_date, scope)
        if picking_id or batch_id:
            self._mobile_target(warehouse_id, picking_id, batch_id)
        return {'type': 'ir.actions.client', 'name': _('Recolección'),
                'tag': 'operations_dashboard.mobile_pick',
                'params': {'warehouse_id': warehouse_id, 'date': selected_date, 'scope': scope,
                           'picking_id': picking_id, 'batch_id': batch_id, 'readiness': readiness}}

    def _mobile_target(self, warehouse_id, picking_id=False, batch_id=False):
        warehouse = self._warehouse(warehouse_id)
        pickings, batch = self._guided_pickings(warehouse, 'pick', picking_id, batch_id)
        return warehouse, pickings, batch

    def _mobile_card(self, pickings, batch):
        state = 'partial' if any(p.systore_batch_readiness_state == 'partial' for p in pickings) else 'complete'
        # Only the order IDs are used for this inventory summary, not prices or sale access.
        orders = pickings.sudo().sale_id | pickings.sudo().move_ids.sale_line_id.order_id
        return {'key': 'b%s' % batch.id if batch else 'p%s' % pickings.id,
                'batch_id': batch.id if batch else False, 'picking_id': False if batch else pickings.id,
                'name': batch.name if batch else pickings.name,
                'origins': list(dict.fromkeys(filter(None, pickings.mapped('origin')))),
                'operation_type': ', '.join(pickings.picking_type_id.mapped('display_name')),
                'state': state, 'orders': len(orders), 'operations': len(pickings),
                'pieces': sum(self._picking_pieces(p) for p in pickings),
                'blocked': '', 'is_batch': bool(batch),
                'responsible': (batch.user_id.display_name or _('Sin asignar')) if batch else ''}

    @api.model
    def get_mobile_pick_panel(self, warehouse_id, selected_date=False, scope='date', page=0, mode='pending', query='', readiness='complete'):
        warehouse = self._warehouse(warehouse_id)
        day, today, timezone = self._parameters(selected_date, scope)
        if readiness not in ('complete', 'partial', 'all'):
            raise ValidationError(_('Estado inválido.'))
        if mode not in ('pending', 'batches'):
            raise ValidationError(_('Vista de recolección inválida.'))
        if type(page) is not int or page < 0:
            raise ValidationError(_('Página inválida.'))
        pickings = self.env['stock.picking'].search(
            AND([self._section_domain(warehouse, 'pick'),
                 [('state', '!=', 'draft')]]), order='scheduled_date, id')
        groups = {}
        for picking in pickings:
            if mode == 'batches' and not picking.batch_id:
                continue
            key = ('batch', picking.batch_id.id) if mode == 'batches' else ('picking', picking.id)
            groups.setdefault(key, self.env['stock.picking'])
            groups[key] |= picking
        term = self._search_term(query)
        cards = []
        counts = {'complete': 0, 'partial': 0}
        for (kind, record_id), matching in groups.items():
            batch = matching.batch_id if kind == 'batch' else self.env['stock.picking.batch']
            error = ''
            if batch:
                try:
                    matching, batch = self._guided_pickings(warehouse, 'pick', batch_id=record_id)
                except (AccessError, UserError):
                    continue

            official = 'partial' if any(p.systore_batch_readiness_state == 'partial' for p in matching) else 'complete'
            counts[official] += 1
            if readiness != 'all' and official != readiness:
                continue
            card = self._mobile_card(matching, batch)
            card['blocked'] = error
            if not term or term in (' '.join([card['name'], *card['origins'], card['operation_type']]) + ' ' + self._operation_search_text(matching)).casefold():
                cards.append(card)
        return {'warehouse': warehouse.name, 'counts': counts, 'cards': cards[page * 30:(page + 1) * 30], 'page': page,
                'has_more': (page + 1) * 30 < len(cards), 'total': len(cards), 'mode': mode}

    def _mobile_detail(self, warehouse, pickings, batch):
        rows, reasons = [], []
        if any(p.state not in ('assigned', 'confirmed') for p in pickings):
            reasons.append(_('Hay operaciones pendientes de disponibilidad. Complete la etapa anterior o revise la reserva en la vista original.'))
        for picking in pickings:
            moves = picking.move_ids.filtered(lambda m: m.state not in ('done', 'cancel') and m.product_id.type != 'service')
            for move in moves:
                if move.product_uom != move.product_id.uom_id:
                    reasons.append(_('Esta primera pantalla requiere la unidad de inventario del producto. Opere otras unidades desde la vista original.'))
            lines = picking.move_line_ids.filtered(lambda l: l.state not in ('done', 'cancel') and l.quantity > 0)
            for line in lines.sorted(key=lambda l: (l.location_id.complete_name, l.product_id.display_name, l.id)):
                quantity = line.product_uom_id._compute_quantity(line.quantity, line.product_id.uom_id)
                rows.append({'id': line.id, 'picking_id': picking.id, 'operation': picking.name,
                    'origin': picking.origin or '', 'location': line.location_id.complete_name, 'location_id': line.location_id.id,
                    'product_id': line.product_id.id, 'product': line.product_id.display_name,
                    'qty': quantity, 'rounding': line.product_id.uom_id.rounding, 'uom': line.product_id.uom_id.name, 'uom_id': line.product_id.uom_id.id,
                    'lot': line.lot_id.name or '', 'require_upc': picking._systore_needs_upc_picking_wizard()})
        if not rows:
            reasons.append(_('No hay productos para recoger.'))
        rows = group_pick_rows(rows)
        snapshot = {'rows': rows, 'pickings': [(p.id, p.state, str(p.write_date), p.systore_batch_readiness_state) for p in pickings],
                    'moves': [(m.id, m.product_uom_qty, m.product_uom.id, str(m.write_date)) for m in pickings.move_ids],
                    'lines': [(line.id, str(line.write_date)) for line in pickings.move_line_ids]}
        token = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        return {'card': self._mobile_card(pickings, batch), 'rows': rows,
                'token': token, 'can_validate': not reasons, 'notice': '\n'.join(dict.fromkeys(reasons)),
                'warehouse': warehouse.name}

    @api.model
    def get_mobile_pick_detail(self, warehouse_id, picking_id=False, batch_id=False):
        return self._mobile_detail(*self._mobile_target(warehouse_id, picking_id, batch_id))

    @api.model
    def open_mobile_pick_native(self, warehouse_id, picking_id=False, batch_id=False):
        _warehouse, pickings, batch = self._mobile_target(warehouse_id, picking_id, batch_id)
        if batch:
            return {'type': 'ir.actions.act_window', 'res_model': 'stock.picking.batch',
                    'res_id': batch.id, 'views': [(False, 'form')], 'target': 'current'}
        return {'type': 'ir.actions.act_window', 'res_model': 'stock.picking',
                'res_id': pickings.id, 'views': [(False, 'form')], 'target': 'current'}

    @api.model
    def check_mobile_pick_upc(self, warehouse_id, picking_id, batch_id, token, product_id, barcode):
        detail = self._mobile_detail(*self._mobile_target(warehouse_id, picking_id, batch_id))
        if token != detail['token']:
            raise UserError(_('La operación o su reserva cambió. Vuelva al panel y abra la recolección nuevamente.'))
        if not detail['can_validate']:
            raise UserError(detail['notice'])
        if type(product_id) is not int or product_id not in {row['product_id'] for row in detail['rows']}:
            raise AccessError(_('El producto no pertenece a esta recolección.'))
        if not isinstance(barcode, str) or not barcode.strip() or len(barcode) > 256:
            raise ValidationError(_('Capture un UPC válido.'))
        # A virtual line reuses the installed validator without creating a wizard,
        # changing stock quantities, or marking the picking as validated.
        line = self.env['stock.picking.upc.wizard.line'].with_context(systore_operations_mobile=True).new({
            'product_id': product_id, 'upc_ean': barcode.strip(), 'skip_upc_validation': False})
        line._validate_scanned_barcode()
        return {'product_id': product_id, 'upc': line.upc_ean, 'valid': True}

    @api.model
    def validate_mobile_pick(self, warehouse_id, picking_id, batch_id, token, captures):
        warehouse, pickings, batch = self._mobile_target(warehouse_id, picking_id, batch_id)
        # Serialize competing mobile validations and recheck real reservations, never trust client totals.
        pickings.flush_recordset()
        self.env['stock.move'].flush_model()
        self.env['stock.move.line'].flush_model()
        self.env.cr.execute('SELECT id FROM stock_picking WHERE id IN %s ORDER BY id FOR UPDATE', (tuple(pickings.ids),))
        for table, records in [('stock_move', pickings.move_ids), ('stock_move_line', pickings.move_line_ids)]:
            if records:
                self.env.cr.execute('SELECT id FROM ' + table + ' WHERE id IN %s ORDER BY id FOR UPDATE', (tuple(records.ids),))
                records.invalidate_recordset()
        pickings.invalidate_recordset()
        if batch:
            batch.invalidate_recordset()
        warehouse, pickings, batch = self._mobile_target(warehouse_id, picking_id, batch_id)
        detail = self._mobile_detail(warehouse, pickings, batch)
        if token != detail['token']:
            raise UserError(_('La operación o su reserva cambió. Vuelva al panel y abra la recolección nuevamente.'))
        if not detail['can_validate']:
            raise UserError(detail['notice'])
        try:
            values = normalize_capture(detail['rows'], captures)
        except ValueError as error:
            raise ValidationError(str(error)) from error
        lines = pickings.move_line_ids.filtered(lambda line: line.state not in ('done', 'cancel') and line.quantity > 0)
        capacities = {line.id: line.product_uom_id._compute_quantity(line.quantity, line.product_id.uom_id) for line in lines}
        try:
            allocated = allocate_pick_quantities(detail['rows'], values, capacities)
        except (ValueError, KeyError) as error:
            raise ValidationError(_('La cantidad supera la reserva de esta ubicación.')) from error
        # Validate every selected product/location through the installed UPC validator.
        Validator = self.env['stock.picking.upc.wizard.line'].with_context(systore_operations_mobile=True)
        for row in detail['rows']:
            capture = values[row['id']]
            if row['require_upc'] and capture['quantity'] > 0:
                virtual = Validator.new({'product_id': row['product_id'], 'upc_ean': capture['upc'],
                                         'skip_upc_validation': False})
                virtual._validate_scanned_barcode()
        targets = pickings.filtered(lambda picking: any(allocated.get(line.id, 0) > 0 for line in picking.move_line_ids))
        if not targets:
            raise ValidationError(_('Registre al menos una pieza para validar.'))
        if any(self._requires_full_capture(picking) for picking in targets):
            raise UserError(_('Esta etapa requiere la pantalla de UPC, series y guía. Vuelva a abrirla desde el tablero.'))
        if batch and batch.state == 'draft':
            batch.action_confirm()
        if not {line_id for line_id, quantity in allocated.items() if quantity > 0}.issubset(set(targets.move_line_ids.ids)):
            raise UserError(_('Las líneas de reserva cambiaron. Vuelva a abrir la operación.'))
        for line in targets.move_line_ids.filtered(lambda line: line.state not in ('done', 'cancel')):
            available = line.product_uom_id._compute_quantity(line.quantity, line.product_id.uom_id)
            if float_compare(allocated.get(line.id, 0), available, precision_rounding=line.product_id.uom_id.rounding) > 0:
                raise UserError(_('La reserva cambió al confirmar el lote. Vuelva a abrirlo.'))
            line.quantity = line.product_id.uom_id._compute_quantity(allocated.get(line.id, 0), line.product_uom_id)
        # Preserve original locations, native lots and packages. Never redistribute a
        # partial batch by product across other orders or locations.
        targets.move_ids.filtered(lambda move: move.state not in ('done', 'cancel') and move.quantity > 0).write({'picked': True})
        checked = targets.filtered(lambda picking: picking._systore_needs_upc_picking_wizard())
        if checked:
            checked.write({'systore_upc_picking_validated': True})
        # UPC was checked above; all remaining native hooks and backorders still run.
        result = targets.with_context(systore_skip_upc_picking_wizard=True).button_validate()
        return {'action': result if isinstance(result, dict) and result.get('type') != 'ir.actions.act_window_close' else False,
                'complete': all(p.state == 'done' for p in targets)}
