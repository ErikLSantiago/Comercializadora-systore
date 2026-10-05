import hashlib
import json

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class MobilePackService(models.AbstractModel):
    _inherit = 'systore.operations.dashboard'

    @api.model
    def open_mobile_pack(self, warehouse_id, picking_id=False, batch_id=False):
        warehouse = self._warehouse(warehouse_id)
        if picking_id or batch_id:
            self._guided_pickings(warehouse, 'pack', picking_id, batch_id)
        return {'type': 'ir.actions.client', 'name': _('Empaquetado'),
                'tag': 'systore_operations_dashboard.mobile_pack',
                'params': {'warehouse_id': warehouse_id, 'picking_id': picking_id, 'batch_id': batch_id}}

    @api.model
    def get_mobile_pack_panel(self, warehouse_id, batch_id=False, page=0, query=''):
        warehouse = self._warehouse(warehouse_id)
        if type(page) is not int or page < 0:
            raise ValidationError(_('Página inválida.'))
        if batch_id:
            pickings, _batch = self._guided_pickings(warehouse, 'pack', batch_id=batch_id)
        else:
            pickings = self.env['stock.picking'].search(self._section_domain(warehouse, 'pack'), order='scheduled_date,id')
        term = self._search_term(query)
        pickings = pickings.filtered(lambda p: p.state == 'assigned')
        if term:
            pickings = pickings.filtered(lambda p: term in ' '.join([p.name, p.systore_operations_sale_names or p.origin or '', self._operation_search_text(p)]).casefold())
        return {'warehouse': warehouse.name, 'total': len(pickings), 'has_more': len(pickings) > (page + 1) * 30,
                'cards': [{'picking_id': p.id, 'key': str(p.id), 'name': p.name,
                           'origins': [p.systore_operations_sale_names or p.origin or ''],
                           'operation_type': p.picking_type_id.name, 'state': p.state,
                           'pieces': self._picking_pieces(p), 'batch': p.batch_id.name or ''}
                          for p in pickings[page * 30:(page + 1) * 30]]}

    @api.model
    def open_mobile_pack_native(self, warehouse_id, picking_id):
        warehouse = self._warehouse(warehouse_id)
        picking, _batch = self._guided_pickings(warehouse, 'pack', picking_id=picking_id)
        return {'type': 'ir.actions.act_window', 'res_model': 'stock.picking', 'res_id': picking.id,
                'views': [(False, 'form')], 'target': 'current'}

    def _pack_token(self, picking):
        payload = [(picking.id, picking.state, str(picking.write_date)),
                   [(m.id, m.quantity, m.product_uom_qty, str(m.write_date)) for m in picking.move_ids],
                   [(m.id, str(m.write_date)) for m in picking.move_line_ids]]
        return hashlib.sha256(json.dumps(payload).encode()).hexdigest()

    @api.model
    def get_mobile_pack_detail(self, warehouse_id, picking_id):
        warehouse = self._warehouse(warehouse_id)
        picking, _batch = self._guided_pickings(warehouse, 'pack', picking_id=picking_id)
        moves = picking.move_ids_without_package.filtered(lambda m: m.state not in ('done', 'cancel'))
        if any(m.product_uom != m.product_id.uom_id or m.product_uom_qty != int(m.product_uom_qty) for m in moves):
            raise UserError(_('Use la vista original para cantidades fraccionarias u otras unidades.'))
        action = self.open_guided_operation(warehouse_id, 'pack', scope='all', picking_id=picking_id)
        wizard = self.env['stock.picking.upc.wizard'].browse(action['res_id'])
        return {'picking_id': picking.id, 'state': picking.state, 'wizard_id': wizard.id, 'token': self._pack_token(picking), 'name': picking.name,
                'orders': picking.systore_operations_sale_names or picking.origin or '',
                'source': picking.location_id.complete_name, 'destination': picking.location_dest_id.complete_name,
                'rows': [{'id': line.id, 'product_id': line.product_id.id, 'product': line.product_id.display_name,
                          'scan_no': line.scan_no, 'qty': line.demand_qty} for line in wizard.line_ids]}

    def _pack_wizard(self, warehouse_id, wizard_id, token):
        warehouse = self._warehouse(warehouse_id)
        if type(wizard_id) is not int:
            raise ValidationError(_('Preparación inválida.'))
        wizard = self.env['stock.picking.upc.wizard'].browse(wizard_id).exists()
        if not wizard or wizard.create_uid != self.env.user or wizard.systore_guided_warehouse_id != warehouse or wizard.systore_guided_section != 'pack' or wizard.batch_id:
            raise AccessError(_('Esta preparación no está disponible para este usuario y almacén.'))
        wizard.check_access('write')
        picking, _batch = self._guided_pickings(warehouse, 'pack', picking_id=wizard.picking_id.id)
        if picking.state != 'assigned' or token != self._pack_token(picking):
            raise UserError(_('La operación cambió. Vuelva a abrirla antes de continuar.'))
        if not picking.systore_require_tracking_on_pack or not picking._systore_needs_upc_picking_wizard():
            raise UserError(_('Revise la configuración o el asistente pendiente desde la vista original.'))
        return wizard.with_context(systore_operations_mobile=True)

    def _pack_text(self, value, label):
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            raise ValidationError(_('Capture %s válido.') % label)
        return value.strip()

    @api.model
    def check_mobile_pack_piece(self, warehouse_id, wizard_id, token, line_id, upc, serial=False):
        wizard = self._pack_wizard(warehouse_id, wizard_id, token)
        if type(line_id) is not int or line_id not in wizard.line_ids.ids:
            raise AccessError(_('La pieza no pertenece a esta preparación.'))
        line = wizard.line_ids.filtered(lambda line: line.id == line_id)
        values = {'product_id': line.product_id.id, 'upc_ean': self._pack_text(upc, 'UPC'), 'skip_upc_validation': False}
        virtual = self.env['stock.picking.upc.wizard.line'].with_context(systore_operations_mobile=True).new(values)
        virtual._validate_scanned_barcode()
        if serial is not False:
            virtual.serial_imei = self._pack_text(serial, 'NS/IMEI')
            virtual._validate_serial_imei()
        return {'upc': virtual.upc_ean, 'serial': virtual.serial_imei or ''}

    @api.model
    def validate_mobile_pack(self, warehouse_id, wizard_id, token, captures, tracking):
        wizard = self._pack_wizard(warehouse_id, wizard_id, token)
        picking = wizard.picking_id
        self.env.flush_all()
        for table, records in [('stock_picking', picking), ('stock_move', picking.move_ids), ('stock_move_line', picking.move_line_ids)]:
            if records:
                self.env.cr.execute('SELECT id FROM ' + table + ' WHERE id IN %s ORDER BY id FOR UPDATE', (tuple(records.ids),))
                records.invalidate_recordset()
        wizard = self._pack_wizard(warehouse_id, wizard_id, token)
        if not isinstance(captures, list) or len(captures) != len(wizard.line_ids):
            raise ValidationError(_('Complete todas las piezas.'))
        seen, serials = set(), set()
        for capture in captures:
            if not isinstance(capture, dict) or type(capture.get('id')) is not int or capture['id'] in seen or capture['id'] not in wizard.line_ids.ids:
                raise ValidationError(_('Pieza inválida o repetida.'))
            seen.add(capture['id'])
            serial = self._pack_text(capture.get('serial'), 'NS/IMEI')
            if serial in serials:
                raise ValidationError(_('El NS/IMEI ya fue capturado en este empaque.'))
            serials.add(serial)
            line = wizard.line_ids.filtered(lambda line: line.id == capture['id'])
            line.write({'upc_ean': self._pack_text(capture.get('upc'), 'UPC'), 'serial_imei': serial,
                        'skip_upc_validation': False, 'demand_qty': 1})
        wizard.tracking_ref = self._pack_text(tracking, 'número de guía')
        result = wizard.action_confirm()
        return {'complete': picking.state == 'done',
                'action': result if isinstance(result, dict) and result.get('type') != 'ir.actions.act_window_close' else False}
