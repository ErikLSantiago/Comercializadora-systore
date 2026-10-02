import hashlib
import json

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv.expression import AND
from odoo.tools.float_utils import float_compare

from .date_policy import matches_scope
from .receipt_policy import receipt_captures


class _ReceiptPreviewRollback(Exception):
    """Rollback the installed registration routine after a successful preview."""


class MobileReceiptService(models.AbstractModel):
    _inherit = 'systore.operations.dashboard'

    @api.model
    def open_mobile_receipt(self, warehouse_id, selected_date=False, scope='date', purchase_id=False):
        self._warehouse(warehouse_id)
        self._parameters(selected_date, scope)
        if purchase_id and type(purchase_id) is not int:
            raise ValidationError(_('Compra inválida.'))
        return {'type': 'ir.actions.client', 'name': _('Ingresos'),
                'tag': 'systore_operations_dashboard.mobile_receipt',
                'params': {'warehouse_id': warehouse_id, 'date': selected_date,
                           'scope': scope, 'purchase_id': purchase_id}}

    def _receipt_target(self, warehouse_id, picking_id, purchase_id=False):
        warehouse = self._warehouse(warehouse_id)
        if type(picking_id) is not int or not picking_id:
            raise ValidationError(_('Recepción inválida.'))
        domain = AND([self._section_domain(warehouse, 'in'), [('id', '=', picking_id)]])
        if purchase_id:
            if type(purchase_id) is not int:
                raise ValidationError(_('Compra inválida.'))
            domain = AND([domain, [('systore_operations_purchase_ids', 'in', [purchase_id])]])
        picking = self.env['stock.picking'].search(domain, limit=1)
        if not picking:
            raise AccessError(_('La recepción no está disponible en este almacén o ya fue validada.'))
        picking.check_access('write')
        return warehouse, picking

    @api.model
    def get_mobile_receipt_panel(self, warehouse_id, selected_date=False, scope='date', purchase_id=False, page=0):
        warehouse = self._warehouse(warehouse_id)
        day, today, timezone = self._parameters(selected_date, scope)
        if type(page) is not int or page < 0 or (purchase_id and type(purchase_id) is not int):
            raise ValidationError(_('Filtro inválido.'))
        pickings = self.env['stock.picking'].search(self._section_domain(warehouse, 'in'), order='scheduled_date,id')
        entries = [entry for entry in self._receipt_entries(pickings)
                   if (not purchase_id or entry['purchase_id'] == purchase_id)
                   and matches_scope(entry['date'], scope, day, today, timezone)]
        by_id = {p.id: p for p in pickings}
        cards = []
        for entry in entries[page * 30:(page + 1) * 30]:
            receipts = [{'picking_id': pid, 'name': by_id[pid].name, 'state': by_id[pid].state,
                         'pieces': self._picking_pieces(by_id[pid])} for pid in entry['picking_ids']]
            cards.append({'key': entry['key'], 'purchase_id': entry['purchase_id'],
                'name': entry['label'], 'origins': [entry['label']], 'operation_type': 'Ingresos',
                'supplier': entry['partner'], 'supplier_ref': entry['supplier_ref'],
                'packages': entry['packages'], 'pieces': sum(r['pieces'] for r in receipts),
                'receipts': receipts})
        return {'warehouse': warehouse.name, 'cards': cards, 'page': page,
                'has_more': (page + 1) * 30 < len(entries), 'total': len(entries)}

    def _receipt_detail(self, warehouse, picking):
        reasons = []
        if picking.state not in ('assigned', 'confirmed'):
            reasons.append(_('Confirme la compra y complete los pasos previos antes de ingresar.'))
        moves = picking.move_ids_without_package.filtered(lambda m: m.state not in ('done', 'cancel'))
        if any(move.product_uom != move.product_id.uom_id for move in moves):
            reasons.append(_('Utilice la vista original para productos con otra unidad de medida.'))
        rows = []
        required = picking._systore_needs_upc_receipt_wizard()
        for group in picking._systore_receipt_validation_groups():
            product = self.env['product.product'].browse(group['product_id'])
            rows.append({'id': str(product.id), 'product_id': product.id, 'product': product.display_name,
                         'qty': group['demand_qty'], 'quantity': min(group['quantity'], group['demand_qty']),
                         'uom': product.uom_id.name, 'require_upc': required})
        if not rows:
            reasons.append(_('No hay productos pendientes de ingresar.'))
        snapshot = {'rows': rows, 'picking': (picking.id, picking.state, str(picking.write_date)),
                    'moves': [(m.id, m.product_uom_qty, m.quantity, str(m.write_date)) for m in moves],
                    'lines': [(line.id, str(line.write_date)) for line in picking.move_line_ids]}
        return {'warehouse': warehouse.name, 'picking_id': picking.id, 'name': picking.name,
                'purchase_names': picking.systore_operations_purchase_names or picking.origin or '',
                'supplier_ref': picking.systore_operations_supplier_refs or '',
                'source': picking.location_id.complete_name, 'destination': picking.location_dest_id.complete_name,
                'supplier': picking.partner_id.display_name or '', 'rows': rows,
                'multi_purchase': len(picking.systore_operations_purchase_ids) > 1,
                'can_validate': not reasons, 'notice': '\n'.join(reasons),
                'token': hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()}

    @api.model
    def get_mobile_receipt_detail(self, warehouse_id, picking_id, purchase_id=False):
        return self._receipt_detail(*self._receipt_target(warehouse_id, picking_id, purchase_id))

    @api.model
    def open_mobile_receipt_native(self, warehouse_id, picking_id, purchase_id=False):
        _warehouse, picking = self._receipt_target(warehouse_id, picking_id, purchase_id)
        return {'type': 'ir.actions.act_window', 'res_model': 'stock.picking', 'res_id': picking.id,
                'views': [(False, 'form')], 'target': 'current'}

    @api.model
    def check_mobile_receipt_upc(self, warehouse_id, picking_id, purchase_id, token, product_id, barcode):
        detail = self.get_mobile_receipt_detail(warehouse_id, picking_id, purchase_id)
        if detail['token'] != token:
            raise UserError(_('La recepción cambió. Vuelva a abrirla antes de continuar.'))
        if not detail['can_validate']:
            raise UserError(detail['notice'])
        if type(product_id) is not int or product_id not in {r['product_id'] for r in detail['rows']}:
            raise AccessError(_('El producto no pertenece a esta recepción.'))
        if not isinstance(barcode, str) or not barcode.strip() or len(barcode) > 256:
            raise ValidationError(_('Capture un UPC válido.'))
        barcode = barcode.strip()
        # The supplied receipt addon registers unknown codes. Preview its exact
        # rules inside a rolled-back savepoint, and register only on confirmation.
        try:
            with self.env.cr.savepoint():
                line = self.env['stock.receipt.upc.wizard.line'].with_context(systore_operations_mobile=True).new({
                    'product_id': product_id, 'upc_ean': barcode, 'skip_upc_validation': False})
                line._validate_and_register_barcode()
                raise _ReceiptPreviewRollback()
        except _ReceiptPreviewRollback:
            pass
        return {'valid': True, 'upc': barcode, 'product_id': product_id}

    @api.model
    def validate_mobile_receipt(self, warehouse_id, picking_id, purchase_id, token, captures):
        warehouse, picking = self._receipt_target(warehouse_id, picking_id, purchase_id)
        picking.flush_recordset()
        self.env['stock.move'].flush_model()
        self.env['stock.move.line'].flush_model()
        for table, records in [('stock_picking', picking), ('stock_move', picking.move_ids),
                               ('stock_move_line', picking.move_line_ids)]:
            if records:
                self.env.cr.execute('SELECT id FROM ' + table + ' WHERE id IN %s ORDER BY id FOR UPDATE', (tuple(records.ids),))
                records.invalidate_recordset()
        warehouse, picking = self._receipt_target(warehouse_id, picking_id, purchase_id)
        detail = self._receipt_detail(warehouse, picking)
        if detail['token'] != token:
            raise UserError(_('La recepción cambió. Vuelva a abrirla antes de continuar.'))
        if not detail['can_validate']:
            raise UserError(detail['notice'])
        try:
            values = receipt_captures(detail['rows'], captures)
        except ValueError as error:
            raise ValidationError(str(error)) from error
        required = picking._systore_needs_upc_receipt_wizard()
        wizard = self.env['stock.receipt.upc.wizard'].with_context(systore_operations_mobile=True).create_from_picking(picking)
        if set(wizard.line_ids.product_id.ids) != set(values):
            raise UserError(_('Los productos pendientes cambiaron. Actualice la recepción.'))
        for line in wizard.line_ids:
            line.write({'quantity': values[line.product_id.id]['quantity'],
                        'upc_ean': values[line.product_id.id]['upc'], 'skip_upc_validation': False})
            line._validate_quantity()
        if required:
            result = wizard.action_confirm()
        else:
            wizard._apply_received_quantities()
            result = picking.button_validate()
        return {'action': result if isinstance(result, dict) and result.get('type') != 'ir.actions.act_window_close' else False,
                'complete': picking.state == 'done'}


class MobileReceiptUPCLine(models.TransientModel):
    _inherit = 'stock.receipt.upc.wizard.line'

    def _validate_and_register_barcode(self):
        try:
            return super()._validate_and_register_barcode()
        except ValidationError:
            if self.env.context.get('systore_operations_mobile'):
                raise ValidationError(_('No coincide UPC/IMEI')) from None
            raise


class MobileReceiptUPCWizard(models.TransientModel):
    _inherit = 'stock.receipt.upc.wizard'

    def _apply_received_quantities(self):
        result = super()._apply_received_quantities()
        if self.env.context.get('systore_operations_mobile'):
            for line in self.line_ids:
                moves = self.picking_id.move_ids_without_package.filtered(
                    lambda m: m.state not in ('done', 'cancel') and m.product_id == line.product_id)
                quantity = sum(moves.mapped('quantity'))
                if float_compare(quantity, line.quantity, precision_rounding=line.product_id.uom_id.rounding):
                    raise UserError(_('La cantidad aplicada por el asistente instalado no coincide con la capturada. Revise esta recepción desde la vista original.'))
        return result
