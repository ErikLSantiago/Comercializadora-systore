import hashlib
import json

from odoo import api, models, Command, _
from odoo.exceptions import AccessError, UserError, ValidationError


class MobilePackService(models.AbstractModel):
    _inherit = 'systore.operations.dashboard'

    def _mobile_pack_section(self, warehouse, section):
        if section not in ('pack', 'out') or (section == 'out' and warehouse.delivery_steps != 'ship_only'):
            raise ValidationError(_('Esta captura corresponde a Empaquetado o a Salidas de un paso.'))
        # Validate the section; subsequent picking reads apply the enabled-type domain.
        self._section_domain(warehouse, section)
        return section

    def _requires_full_capture(self, picking):
        native_policy = getattr(picking, '_systore_requires_full_pack_validation', None)
        return native_policy() if native_policy else bool(picking.systore_require_tracking_on_pack)

    @api.model
    def open_mobile_pack(self, warehouse_id, picking_id=False, batch_id=False, section='pack'):
        warehouse = self._warehouse(warehouse_id)
        self._mobile_pack_section(warehouse, section)
        if picking_id or batch_id:
            self._guided_pickings(warehouse, section, picking_id, batch_id)
        return {'type': 'ir.actions.client', 'name': _('Salidas') if section == 'out' else _('Empaquetado'),
                'tag': 'operations_dashboard.mobile_pack',
                'params': {'warehouse_id': warehouse_id, 'picking_id': picking_id, 'batch_id': batch_id, 'section': section}}

    @api.model
    def get_mobile_pack_panel(self, warehouse_id, batch_id=False, page=0, query='', section='pack'):
        warehouse = self._warehouse(warehouse_id)
        self._mobile_pack_section(warehouse, section)
        if type(page) is not int or page < 0:
            raise ValidationError(_('Página inválida.'))
        if batch_id:
            pickings, _batch = self._guided_pickings(warehouse, section, batch_id=batch_id)
        else:
            pickings = self.env['stock.picking'].search(self._section_domain(warehouse, section), order='scheduled_date,id')
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
    def open_mobile_pack_native(self, warehouse_id, picking_id, section='pack'):
        warehouse = self._warehouse(warehouse_id)
        self._mobile_pack_section(warehouse, section)
        picking, _batch = self._guided_pickings(warehouse, section, picking_id=picking_id)
        return {'type': 'ir.actions.act_window', 'res_model': 'stock.picking', 'res_id': picking.id,
                'views': [(False, 'form')], 'target': 'current'}

    def _pack_token(self, picking):
        payload = [(picking.id, picking.state, str(picking.write_date)),
                   [(m.id, m.quantity, m.product_uom_qty, str(m.write_date)) for m in picking.move_ids],
                   [(m.id, str(m.write_date)) for m in picking.move_line_ids]]
        return hashlib.sha256(json.dumps(payload).encode()).hexdigest()

    @api.model
    def get_mobile_pack_detail(self, warehouse_id, picking_id, section='pack'):
        warehouse = self._warehouse(warehouse_id)
        self._mobile_pack_section(warehouse, section)
        picking, _batch = self._guided_pickings(warehouse, section, picking_id=picking_id)
        moves = picking.move_ids_without_package.filtered(lambda m: m.state not in ('done', 'cancel'))
        if any(m.product_uom != m.product_id.uom_id or m.product_uom_qty != int(m.product_uom_qty) for m in moves):
            raise UserError(_('Use la vista original para cantidades fraccionarias u otras unidades.'))
        action = self._prepare_guided_capture(warehouse, section, picking, _batch)
        wizard = self.env['stock.picking.upc.wizard'].browse(action['res_id'])
        return {'picking_id': picking.id, 'state': picking.state, 'wizard_id': wizard.id, 'token': self._pack_token(picking), 'name': picking.name,
                'orders': picking.systore_operations_sale_names or picking.origin or '',
                'source': picking.location_id.complete_name, 'destination': picking.location_dest_id.complete_name,
                'mass_capture_available': bool(getattr(wizard, 'mass_capture_available', False)),
                'skip_tracking_available': 'skip_tracking_ref' in wizard._fields,
                'rows': [{'id': line.id, 'product_id': line.product_id.id, 'product': line.product_id.display_name,
                          'scan_no': line.scan_no, 'qty': line.demand_qty} for line in wizard.line_ids]}

    def _pack_wizard(self, warehouse_id, wizard_id, token):
        warehouse = self._warehouse(warehouse_id)
        if type(wizard_id) is not int:
            raise ValidationError(_('Preparación inválida.'))
        wizard = self.env['stock.picking.upc.wizard'].browse(wizard_id).exists()
        if not wizard or wizard.create_uid != self.env.user or wizard.systore_guided_warehouse_id != warehouse or wizard.systore_guided_section not in ('pack', 'out') or wizard.batch_id:
            raise AccessError(_('Esta preparación no está disponible para este usuario y almacén.'))
        wizard.check_access('write')
        section = self._mobile_pack_section(warehouse, wizard.systore_guided_section)
        picking, _batch = self._guided_pickings(warehouse, section, picking_id=wizard.picking_id.id)
        if picking.state != 'assigned' or token != self._pack_token(picking):
            raise UserError(_('La operación cambió. Vuelva a abrirla antes de continuar.'))
        if not self._requires_full_capture(picking) or not picking._systore_needs_upc_picking_wizard():
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
    def validate_mobile_pack(self, warehouse_id, wizard_id, token, captures, tracking, capture_massive=False, skip_tracking=False):
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
                raise ValidationError(_('El NS/IMEI ya fue capturado en esta operación.'))
            serials.add(serial)
            line = wizard.line_ids.filtered(lambda line: line.id == capture['id'])
            line.write({'upc_ean': self._pack_text(capture.get('upc'), 'UPC'), 'serial_imei': serial,
                        'skip_upc_validation': False, 'demand_qty': 1})
        if type(capture_massive) is not bool or type(skip_tracking) is not bool:
            raise ValidationError(_('Opciones de captura inválidas.'))
        if skip_tracking:
            if 'skip_tracking_ref' not in wizard._fields:
                raise UserError(_('Actualice Stock UPC Validation para omitir la guía.'))
            wizard.skip_tracking_ref = True
            wizard.tracking_ref = False
        else:
            if 'skip_tracking_ref' in wizard._fields:
                wizard.skip_tracking_ref = False
            wizard.tracking_ref = self._pack_text(tracking, 'número de guía')
        if capture_massive:
            if not getattr(wizard, 'mass_capture_available', False):
                raise UserError(_('Esta versión de Stock UPC Validation no admite captura masiva.'))
            by_product = {}
            for line in wizard.line_ids:
                group = by_product.setdefault(line.product_id.id, {'upc': line.upc_ean, 'serials': []})
                if group['upc'] != line.upc_ean:
                    raise ValidationError(_('La captura masiva requiere un UPC por producto.'))
                group['serials'].append(line.serial_imei)
            # The installed addon owns grouping, quantity checks and serial creation.
            values = wizard._prepare_picking_line_values(picking, capture_massive=True)
            wizard._validate_prepared_line_values(picking, values)
            if set(by_product) != {value['product_id'] for value in values}:
                raise UserError(_('Los productos cambiaron. Vuelva a abrir la operación.'))
            for value in values:
                group = by_product[value['product_id']]
                value.update(upc_ean=group['upc'], processed_qty=len(group['serials']),
                             systore_requested_qty=value['demand_qty'])
            wizard.write({'capture_massive': True,
                          'line_ids': [Command.clear()] + [Command.create(value) for value in values]})
            action = wizard.action_confirm()
            if not isinstance(action, dict) or action.get('res_model') != 'stock.picking.mass.serial.wizard':
                raise UserError(_('Stock UPC Validation no devolvió el asistente masivo esperado.'))
            serial_wizard = self.env['stock.picking.mass.serial.wizard'].browse(action['res_id']).exists()
            if not serial_wizard or serial_wizard.upc_wizard_id != wizard:
                raise AccessError(_('Asistente de series inválido.'))
            for product_id, group in by_product.items():
                lines = serial_wizard.line_ids.filtered(lambda line: line.product_id.id == product_id).sorted('id')
                if len(lines) != len(group['serials']):
                    raise ValidationError(_('La cantidad de series no coincide con las piezas.'))
                for line, serial in zip(lines, group['serials']):
                    line.serial_imei = serial
            result = serial_wizard.action_confirm()
        else:
            result = wizard.action_confirm()
        return {'complete': picking.state == 'done',
                'action': result if isinstance(result, dict) and result.get('type') != 'ir.actions.act_window_close' else False}
