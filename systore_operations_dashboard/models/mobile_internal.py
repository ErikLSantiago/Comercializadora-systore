import hashlib
import json
import math
from odoo import api, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv.expression import AND


class MobileInternal(models.AbstractModel):
    _inherit = 'systore.operations.dashboard'

    def _internal_warehouse(self, warehouse_id, section):
        if section not in ('storage', 'transfers'):
            raise ValidationError(_('Operación inválida.'))
        return self._warehouse(warehouse_id)

    def _internal_target(self, warehouse_id, section, picking_id):
        warehouse = self._internal_warehouse(warehouse_id, section)
        if type(picking_id) is not int:
            raise ValidationError(_('Transferencia inválida.'))
        picking = self.env['stock.picking'].search(AND([self._section_domain(warehouse, section), [('id', '=', picking_id)]]), limit=1)
        if not picking:
            raise AccessError(_('La operación no está lista o no está disponible en este almacén.'))
        picking.check_access('write')
        return picking

    @api.model
    def open_mobile_internal(self, warehouse_id, section, selected_date=False, scope='all'):
        self._internal_warehouse(warehouse_id, section)
        self._parameters(selected_date, scope)
        return {'type': 'ir.actions.client', 'tag': 'systore_operations_dashboard.mobile_internal',
                'name': _('Almacenamiento') if section == 'storage' else _('Transferencias'),
                'params': {'warehouse_id': warehouse_id, 'section': section, 'date': selected_date, 'scope': scope}}

    @api.model
    def get_mobile_internal_panel(self, warehouse_id, section, selected_date=False, scope='all', page=0, query=''):
        warehouse = self._internal_warehouse(warehouse_id, section)
        day, today, timezone = self._parameters(selected_date, scope)
        if type(page) is not int or page < 0:
            raise ValidationError(_('Página inválida.'))
        picks = self.env['stock.picking'].search(self._filtered_domain(warehouse, section, day, scope, today, timezone), order='scheduled_date,id')
        term = self._search_term(query)
        if term:
            picks = picks.filtered(lambda p: term in ' '.join([p.name, p.origin or '', self._operation_search_text(p)]).casefold())
        return {'warehouse': warehouse.name, 'has_more': len(picks) > (page + 1) * 30,
                'cards': [{'key': str(p.id), 'picking_id': p.id, 'name': p.name, 'origins': [p.origin or ''],
                           'operation_type': p.picking_type_id.name, 'pieces': self._picking_pieces(p),
                           'state': p.state} for p in picks[page * 30:(page + 1) * 30]]}

    def _internal_detail(self, picking):
        moves = picking.move_ids_without_package.filtered(lambda m: m.state not in ('done', 'cancel'))
        data = [(picking.id, picking.state, str(picking.write_date)),
                [(m.id, m.product_uom_qty, m.quantity, str(m.write_date)) for m in moves],
                [(line.id, str(line.write_date)) for line in picking.move_line_ids]]
        return {'picking_id': picking.id, 'name': picking.name, 'origin': picking.origin or '',
                'token': hashlib.sha256(json.dumps(data).encode()).hexdigest(),
                'rows': [{'id': m.id, 'product_id': m.product_id.id, 'product': m.product_id.display_name,
                          'source': m.location_id.complete_name, 'destination': m.location_dest_id.complete_name,
                          'qty': m.product_uom_qty, 'quantity': m.quantity, 'uom': m.product_uom.name} for m in moves]}

    @api.model
    def get_mobile_internal_detail(self, warehouse_id, section, picking_id):
        return self._internal_detail(self._internal_target(warehouse_id, section, picking_id))

    @api.model
    def open_mobile_internal_native(self, warehouse_id, section, picking_id):
        picking = self._internal_target(warehouse_id, section, picking_id)
        return {'type': 'ir.actions.act_window', 'res_model': 'stock.picking', 'res_id': picking.id,
                'views': [(False, 'form')], 'target': 'current'}

    @api.model
    def validate_mobile_internal(self, warehouse_id, section, picking_id, token, quantities):
        picking = self._internal_target(warehouse_id, section, picking_id)
        self.env.flush_all()
        for table, records in [('stock_picking', picking), ('stock_move', picking.move_ids), ('stock_move_line', picking.move_line_ids)]:
            if records:
                self.env.cr.execute('SELECT id FROM ' + table + ' WHERE id IN %s ORDER BY id FOR UPDATE', (tuple(records.ids),))
                records.invalidate_recordset()
        picking = self._internal_target(warehouse_id, section, picking_id)
        detail = self._internal_detail(picking)
        if token != detail['token']:
            raise UserError(_('La operación cambió. Vuelva a abrirla antes de validar.'))
        expected = {row['id']: row for row in detail['rows']}
        if not isinstance(quantities, list) or len(quantities) != len(expected):
            raise ValidationError(_('Revise los productos de la operación.'))
        captured = {}
        for item in quantities:
            if not isinstance(item, dict) or type(item.get('id')) is not int or item['id'] not in expected or item['id'] in captured:
                raise ValidationError(_('Movimiento inválido o repetido.'))
            quantity = item.get('quantity')
            if type(quantity) not in (int, float) or not math.isfinite(quantity) or quantity < 0 or quantity > expected[item['id']]['qty']:
                raise ValidationError(_('La cantidad debe estar entre cero y las piezas solicitadas.'))
            captured[item['id']] = quantity
        if not any(captured.values()):
            raise ValidationError(_('Registre al menos una pieza.'))
        for move in picking.move_ids_without_package.filtered(lambda m: m.id in captured):
            move.quantity = captured[move.id]
        # Native reservation, lot/serial, packages, routing and backorder hooks.
        result = picking.button_validate()
        return {'complete': picking.state == 'done',
                'action': result if isinstance(result, dict) and result.get('type') != 'ir.actions.act_window_close' else False}
