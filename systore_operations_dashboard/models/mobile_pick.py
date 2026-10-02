import hashlib
import json

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare

from .mobile_pick_policy import normalize_capture, serial_count


class MobilePickDashboard(models.AbstractModel):
    _inherit = 'systore.operations.dashboard'

    @api.model
    def open_mobile_pick(self, warehouse_id, selected_date=False, scope='date', picking_id=False, batch_id=False):
        self._warehouse(warehouse_id)
        self._parameters(selected_date, scope)
        if picking_id or batch_id:
            self._mobile_target(warehouse_id, picking_id, batch_id)
        return {'type': 'ir.actions.client', 'name': _('Recolección'),
                'tag': 'systore_operations_dashboard.mobile_pick',
                'params': {'warehouse_id': warehouse_id, 'date': selected_date, 'scope': scope,
                           'picking_id': picking_id, 'batch_id': batch_id}}

    def _mobile_target(self, warehouse_id, picking_id=False, batch_id=False):
        warehouse = self._warehouse(warehouse_id)
        pickings, batch = self._guided_pickings(warehouse, 'pick', picking_id, batch_id)
        if not batch and pickings.batch_id:
            pickings, batch = self._guided_pickings(warehouse, 'pick', batch_id=pickings.batch_id.id)
        return warehouse, pickings, batch

    def _mobile_card(self, pickings, batch):
        states = set(pickings.mapped('state'))
        state = next(iter(states)) if len(states) == 1 else ('mixed' if 'assigned' in states else 'confirmed')
        # Only the order IDs are used for this inventory summary, not prices or sale access.
        orders = pickings.sudo().sale_id | pickings.sudo().move_ids.sale_line_id.order_id
        return {'key': 'b%s' % batch.id if batch else 'p%s' % pickings.id,
                'batch_id': batch.id if batch else False, 'picking_id': False if batch else pickings.id,
                'name': batch.name if batch else pickings.name,
                'origins': list(dict.fromkeys(filter(None, pickings.mapped('origin')))),
                'operation_type': ', '.join(pickings.picking_type_id.mapped('display_name')),
                'state': state, 'orders': len(orders), 'operations': len(pickings),
                'pieces': sum(self._picking_pieces(p) for p in pickings),
                'blocked': '', 'is_batch': bool(batch)}

    @api.model
    def get_mobile_pick_panel(self, warehouse_id, selected_date=False, scope='date', page=0):
        warehouse = self._warehouse(warehouse_id)
        day, today, timezone = self._parameters(selected_date, scope)
        if type(page) is not int or page < 0:
            raise ValidationError(_('Página inválida.'))
        pickings = self.env['stock.picking'].search(
            self._filtered_domain(warehouse, 'pick', day, scope, today, timezone), order='scheduled_date, id')
        groups = {}
        for picking in pickings:
            key = ('batch', picking.batch_id.id) if picking.batch_id else ('picking', picking.id)
            groups.setdefault(key, self.env['stock.picking'])
            groups[key] |= picking
        cards = []
        for (kind, record_id), matching in list(groups.items())[page * 30:(page + 1) * 30]:
            batch = matching.batch_id if kind == 'batch' else self.env['stock.picking.batch']
            error = ''
            if batch:
                try:
                    matching, batch = self._guided_pickings(warehouse, 'pick', batch_id=record_id)
                except (AccessError, UserError):
                    error = _('El batch contiene operaciones de otra etapa o fuera de sus permisos. Revíselo en la vista original.')
            card = self._mobile_card(matching, batch)
            card['blocked'] = error
            cards.append(card)
        return {'warehouse': warehouse.name, 'cards': cards, 'page': page,
                'has_more': (page + 1) * 30 < len(groups), 'total': len(groups)}

    def _mobile_detail(self, warehouse, pickings, batch):
        rows, reasons = [], []
        if any(p.state != 'assigned' for p in pickings):
            reasons.append(_('Hay operaciones pendientes de disponibilidad. Complete la etapa anterior o revise la reserva en la vista original.'))
        for picking in pickings:
            moves = picking.move_ids.filtered(lambda m: m.state not in ('done', 'cancel') and m.product_id.type != 'service')
            for move in moves:
                if move.product_uom != move.product_id.uom_id:
                    reasons.append(_('Esta primera pantalla requiere la unidad de inventario del producto. Opere otras unidades desde la vista original.'))
                ready = sum(line.product_uom_id._compute_quantity(line.quantity, move.product_uom)
                            for line in move.move_line_ids)
                if float_compare(ready, move.product_uom_qty, precision_rounding=move.product_uom.rounding):
                    reasons.append(_('La cantidad reservada no coincide con la solicitada. Revise la disponibilidad en la vista original.'))
            lines = picking.move_line_ids.filtered(lambda l: l.state not in ('done', 'cancel') and l.quantity > 0)
            for line in lines.sorted(key=lambda l: (l.location_id.complete_name, l.product_id.display_name, l.id)):
                quantity = line.product_uom_id._compute_quantity(line.quantity, line.product_id.uom_id)
                try:
                    serial_count(quantity)
                except ValueError as error:
                    reasons.append(str(error))
                existing = line.serial_captured_ids.sorted('id').mapped('name')
                if line.product_id.tracking == 'serial' and not line.lot_id:
                    reasons.append(_('Asigne la serie nativa reservada desde la vista original antes de recoger.'))
                if existing and picking._systore_needs_upc_picking_wizard() and picking.systore_require_tracking_on_pack:
                    reasons.append(_('Esta preparación con guía ya tiene series registradas. Continúe desde el asistente original para revisarlas.'))
                if len(existing) > quantity:
                    reasons.append(_('Existen más series que piezas reservadas. Revise el registro original.'))
                rows.append({'id': line.id, 'picking_id': picking.id, 'operation': picking.name,
                    'origin': picking.origin or '', 'location': line.location_id.complete_name,
                    'product_id': line.product_id.id, 'product': line.product_id.display_name,
                    'qty': quantity, 'uom': line.product_id.uom_id.name,
                    'tracking': line.product_id.tracking, 'lot': line.lot_id.name or '',
                    'existing_serials': existing, 'require_upc': picking._systore_needs_upc_picking_wizard()})
            if not lines:
                for move in moves:
                    rows.append({'id': -move.id, 'picking_id': picking.id, 'operation': picking.name,
                        'origin': picking.origin or '', 'location': move.location_id.complete_name,
                        'product_id': move.product_id.id, 'product': move.product_id.display_name,
                        'qty': move.product_uom_qty, 'uom': move.product_uom.name,
                        'tracking': move.product_id.tracking, 'lot': '', 'existing_serials': [], 'require_upc': False})
        if not rows:
            reasons.append(_('No hay productos para recoger.'))
        guides = [{'picking_id': p.id, 'name': p.origin or p.name, 'value': p.carrier_tracking_ref or ''}
                  for p in pickings if p._systore_needs_upc_picking_wizard() and p.systore_require_tracking_on_pack]
        snapshot = {'rows': rows, 'pickings': [(p.id, p.state, str(p.write_date)) for p in pickings],
                    'moves': [(m.id, m.product_uom_qty, m.product_uom.id, str(m.write_date)) for m in pickings.move_ids],
                    'guides': guides, 'lines': [(line.id, str(line.write_date)) for line in pickings.move_line_ids]}
        token = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        return {'card': self._mobile_card(pickings, batch), 'rows': rows, 'guides': guides,
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
    def validate_mobile_pick(self, warehouse_id, picking_id, batch_id, token, captures, guides=None):
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
        guides = guides or {}
        if not isinstance(guides, dict):
            raise ValidationError(_('Guías inválidas.'))
        for guide in detail['guides']:
            value = guides.get(str(guide['picking_id']), '')
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValidationError(_('Capture la guía requerida por el tipo de operación.'))
        if batch and batch.state == 'draft':
            batch.action_confirm()
        Wizard = self.env['stock.picking.upc.wizard']
        all_upc = all(p._systore_needs_upc_picking_wizard() for p in pickings)
        batch_upc = batch and all_upc and not any(p.systore_require_tracking_on_pack for p in pickings)
        targets = [pickings] if batch_upc else [p for p in pickings.sorted('id')]
        for target in targets:
            wizard = Wizard
            if batch_upc:
                wizard = Wizard.create_from_batch(batch)
            elif target._systore_needs_upc_picking_wizard():
                wizard = Wizard.create_from_picking(target)
            lines = target.move_line_ids.filtered(lambda l: l.state not in ('done', 'cancel') and l.quantity > 0).sorted('id')
            by_product = {}
            for line in lines:
                by_product.setdefault(line.product_id.id, []).extend(
                    (serial, values[line.id]['upc']) for serial in values[line.id]['serials'])
            if wizard:
                demands = {}
                for wizard_line in wizard.line_ids:
                    product_id = wizard_line.product_id.id
                    demands[product_id] = demands.get(product_id, 0) + wizard_line.demand_qty
                if set(demands) != set(by_product) or any(
                        float_compare(qty, len(by_product[product_id]), precision_rounding=0.00001)
                        for product_id, qty in demands.items()):
                    raise UserError(_('El asistente UPC y las reservas muestran cantidades distintas. Revise los paquetes y cantidades desde la vista original.'))
                for wizard_line in wizard.line_ids.sorted('id'):
                    scanned = by_product[wizard_line.product_id.id]
                    # Delegate product barcode and serial/tracking validation to the installed addon.
                    if wizard.require_serial_imei:
                        serial, barcode = scanned.pop(0)
                        wizard_line.write({'upc_ean': barcode, 'serial_imei': serial})
                    else:
                        codes = {barcode for _serial, barcode in scanned}
                        for code in codes:
                            wizard_line.upc_ean = code
                            wizard_line._validate_scanned_barcode()
                    wizard_line._validate_scanned_barcode()
                if wizard.require_tracking_on_pack:
                    wizard.tracking_ref = guides[str(target.id)].strip()
            if not wizard or not wizard.require_serial_imei:
                additions = []
                for line in lines:
                    existing = set(line.serial_captured_ids.mapped('name'))
                    additions.extend({'move_line_id': line.id, 'name': serial}
                                     for serial in values[line.id]['serials'] if serial not in existing)
                if additions:
                    self.env['stock.move.line.serial'].create(additions)
            result = wizard.action_confirm() if wizard else target.button_validate()
            if isinstance(result, dict) and result.get('type') != 'ir.actions.act_window_close':
                return {'action': result, 'complete': False}
        return {'action': False, 'complete': all(p.state == 'done' for p in pickings)}
