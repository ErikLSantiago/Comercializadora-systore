from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv.expression import AND
from odoo.tools.float_utils import float_compare


class GuidedOperationsService(models.AbstractModel):
    _inherit = 'systore.operations.dashboard'

    @api.model
    def _guided_pickings(self, warehouse, section, picking_id=False, batch_id=False):
        if section not in ('pick', 'pack', 'out'):
            raise ValidationError(_('Esta pantalla corresponde a una etapa de expedición.'))
        batch = self.env['stock.picking.batch']
        if batch_id:
            if isinstance(batch_id, bool) or not isinstance(batch_id, int):
                raise ValidationError(_('Batch inválido.'))
            batch = batch.browse(batch_id).exists()
            if not batch:
                raise UserError(_('El batch ya no existe.'))
            batch.check_access('read')
            pickings = batch.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
        elif picking_id and isinstance(picking_id, int) and not isinstance(picking_id, bool):
            pickings = self.env['stock.picking'].browse(picking_id).exists()
        else:
            raise ValidationError(_('Seleccione una operación o un batch.'))
        if not pickings:
            raise UserError(_('No hay operaciones pendientes. Actualice el tablero.'))
        allowed = self.env['stock.picking'].search(AND([
            self._section_domain(warehouse, section), [('id', 'in', pickings.ids)],
        ]))
        if set(allowed.ids) != set(pickings.ids):
            raise AccessError(_('El batch contiene operaciones fuera de la etapa, almacén o permisos seleccionados.'))
        pickings.check_access('write')
        return pickings, batch

    @api.model
    def open_guided_operation(self, warehouse_id, section, selected_date=False, scope='date',
                              picking_id=False, batch_id=False):
        warehouse = self._warehouse(warehouse_id)
        day, today, timezone = self._parameters(selected_date, scope)
        if section not in ('pick', 'pack', 'out'):
            raise ValidationError(_('Etapa de expedición inválida.'))
        if picking_id or batch_id:
            pickings, batch = self._guided_pickings(warehouse, section, picking_id, batch_id)
        else:
            pickings = self.env['stock.picking'].search(
                self._filtered_domain(warehouse, section, day, scope, today, timezone))
            batch = self.env['stock.picking.batch']
        if section == 'out':
            if not pickings:
                raise UserError(_('No hay salidas pendientes para este filtro.'))
            session = self.env['systore.operations.dispatch.session'].create({
                'warehouse_id': warehouse.id, 'picking_ids': [(6, 0, pickings.ids)],
            })
            return {'type': 'ir.actions.client', 'name': _('Escanear salidas'),
                    'tag': 'systore_operations_dashboard.dispatch', 'params': {'session_id': session.id}}
        per_order_batch = bool(batch_id and (section == 'pack' or
            section == 'pick' and any(p.systore_require_tracking_on_pack for p in pickings)))
        if (not picking_id and not batch_id) or per_order_batch:
            # Pack must retain one tracking number and its serials per order.
            return {'type': 'ir.actions.act_window', 'name': _('Operaciones para preparar'),
                    'res_model': 'stock.picking', 'view_mode': 'list,form', 'target': 'current',
                    'views': [(self.env.ref('systore_operations_dashboard.view_guided_picking_list').id, 'list'), (False, 'form')],
                    'domain': [('id', 'in', pickings.ids)], 'context': dict(self.env.context, create=False)}
        if (section == 'pick' and not batch and pickings.batch_id
                and not pickings.systore_require_tracking_on_pack):
            # Working a batched Pick always opens the whole batch, after permission checks.
            pickings, batch = self._guided_pickings(warehouse, section, batch_id=pickings.batch_id.id)
        if section == 'pick' and not batch and not pickings.batch_id:
            raise UserError(_('Agregue esta recolección a un batch antes de operarla. Use el botón Batches o la acción nativa «Añadir a lote».'))
        if warehouse not in warehouse.company_id.systore_upc_validation_warehouse_ids:
            raise UserError(_('Habilite este almacén en los ajustes de Stock UPC Validation para validar UPC/NS/IMEI.'))
        for picking in pickings:
            if (section == 'pick' and warehouse.delivery_steps == 'pick_ship'
                    and not picking.picking_type_id.systore_require_tracking_on_pack):
                raise UserError(_('En entrega de dos pasos, active «Exigir guía en empaque» en el tipo Pick. La preparación capturará UPC, NS/IMEI y guía por orden antes de avanzar a Salidas.'))
            if section == 'pack' and not picking.picking_type_id.systore_require_tracking_on_pack:
                raise UserError(_('Active «Exigir guía en empaque» en este tipo de operación para capturar UPC, NS/IMEI y guía.'))
            if not picking._systore_needs_upc_picking_wizard():
                raise UserError(_('La operación %s no requiere una nueva validación UPC. Revise los checks del tipo de operación o continúe su asistente pendiente desde el formulario nativo.') % picking.name)
        pickings.action_assign()
        if any(p.state != 'assigned' for p in pickings):
            raise UserError(_('Primero complete la etapa anterior y reserve los productos. Solo se pueden preparar operaciones completamente disponibles.'))
        if batch and batch.state == 'draft':
            batch.action_confirm()
        Wizard = self.env['stock.picking.upc.wizard']
        wizard = Wizard.create_from_batch(batch) if batch else Wizard.create_from_picking(pickings)
        if not wizard.line_ids:
            raise UserError(_('No hay productos para validar.'))
        wizard.write({'systore_guided_warehouse_id': warehouse.id, 'systore_guided_section': section})
        for line in wizard.line_ids:
            line.systore_requested_qty = line.demand_qty
            if not wizard.require_serial_imei:
                line.demand_qty = 0
        return {'type': 'ir.actions.act_window', 'name': _('Preparar batch') if batch else _('Preparar pedido'),
                'res_model': 'stock.picking.upc.wizard', 'res_id': wizard.id, 'view_mode': 'form',
                'views': [(self.env.ref('systore_operations_dashboard.view_guided_upc_form').id, 'form')], 'target': 'current'}

    @api.model
    def open_batches(self, warehouse_id, section='pick', selected_date=False, scope='date'):
        warehouse = self._warehouse(warehouse_id)
        day, today, timezone = self._parameters(selected_date, scope)
        if section not in ('pick', 'pack', 'out'):
            raise ValidationError(_('Etapa inválida.'))
        pickings = self.env['stock.picking'].search(self._filtered_domain(warehouse, section, day, scope, today, timezone))
        return {'type': 'ir.actions.act_window', 'name': _('Lotes de expedición'),
                'res_model': 'stock.picking.batch', 'view_mode': 'list,form',
                'domain': [('id', 'in', pickings.batch_id.ids)],
                'context': dict(self.env.context, default_company_id=warehouse.company_id.id,
                                default_picking_type_id={'pick': warehouse.pick_type_id.id,
                                                         'pack': warehouse.pack_type_id.id,
                                                         'out': warehouse.out_type_id.id}[section])}


class GuidedStockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_systore_guided_operation(self):
        self.ensure_one()
        warehouse = self.picking_type_id.warehouse_id
        section = next((key for key, operation_type in [('pick', warehouse.pick_type_id),
                         ('pack', warehouse.pack_type_id), ('out', warehouse.out_type_id)]
                        if self.picking_type_id == operation_type), False)
        if not section:
            raise UserError(_('Esta operación no corresponde a Pick, Pack ni Out del almacén.'))
        if section == 'pick':
            return self.env['systore.operations.dashboard'].open_mobile_pick(
                warehouse.id, scope='all', picking_id=self.id)
        return self.env['systore.operations.dashboard'].open_guided_operation(
            warehouse.id, section, scope='all', picking_id=self.id)


class GuidedUPCWizard(models.TransientModel):
    _inherit = 'stock.picking.upc.wizard'

    systore_guided_warehouse_id = fields.Many2one('stock.warehouse', readonly=True)
    systore_guided_section = fields.Selection([('pick', 'Recolección'), ('pack', 'Empaquetado')], readonly=True)
    systore_order_names = fields.Char(compute='_compute_guided_names')

    @api.depends('picking_id.systore_operations_sale_names', 'batch_id.picking_ids.systore_operations_sale_names')
    def _compute_guided_names(self):
        for wizard in self:
            pickings = wizard.batch_id.picking_ids if wizard.batch_id else wizard.picking_id
            wizard.systore_order_names = ', '.join(sorted(set(filter(None, pickings.mapped('systore_operations_sale_names')))))

    def action_confirm(self):
        self.ensure_one()
        if not self.systore_guided_warehouse_id:
            return super().action_confirm()
        service = self.env['systore.operations.dashboard']
        warehouse = service._warehouse(self.systore_guided_warehouse_id.id)
        pickings, _batch = service._guided_pickings(warehouse, self.systore_guided_section,
                                                  self.picking_id.id, self.batch_id.id)
        if any(p.state != 'assigned' for p in pickings):
            raise UserError(_('La disponibilidad de la operación cambió. Revise sus reservas antes de validar.'))
        if any(line.skip_upc_validation for line in self.line_ids):
            raise UserError(_('La pantalla guiada exige el UPC. Use el flujo nativo para registrar una excepción autorizada.'))
        requested = {}
        for picking in pickings:
            for group in picking._systore_pick_validation_groups():
                product_id = group['product_id']
                requested[product_id] = requested.get(product_id, 0) + group['demand_qty']
        processed = {}
        for line in self.line_ids:
            if line.demand_qty < 0:
                raise ValidationError(_('Las piezas procesadas no pueden ser negativas.'))
            processed[line.product_id.id] = processed.get(line.product_id.id, 0) + line.demand_qty
        if not any(processed.values()):
            raise UserError(_('Registre las piezas procesadas antes de validar.'))
        for product_id, quantity in processed.items():
            if float_compare(quantity, requested.get(product_id, 0), precision_rounding=0.00001) > 0:
                raise ValidationError(_('Las piezas procesadas exceden la cantidad disponible del producto.'))
        if not self.require_serial_imei:
            self.line_ids.filtered(lambda line: not line.demand_qty).unlink()
        # All barcode checks, quantity application, additional serial creation,
        # tracking propagation and native backorders remain in the supplied addon.
        return super().action_confirm()


class GuidedBatch(models.Model):
    _inherit = 'stock.picking.batch'

    def action_systore_guided_batch(self):
        self.ensure_one()
        pending = self.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
        if not pending:
            raise UserError(_('No hay operaciones pendientes en este batch.'))
        picking = pending[0]
        warehouse = picking.picking_type_id.warehouse_id
        section = next((key for key, operation_type in [('pick', warehouse.pick_type_id),
                         ('pack', warehouse.pack_type_id), ('out', warehouse.out_type_id)]
                        if picking.picking_type_id == operation_type), False)
        if section == 'pick':
            return self.env['systore.operations.dashboard'].open_mobile_pick(
                warehouse.id, scope='all', batch_id=self.id)
        return self.env['systore.operations.dashboard'].open_guided_operation(
            warehouse.id, section, scope='all', batch_id=self.id)


class GuidedUPCWizardLine(models.TransientModel):
    _inherit = 'stock.picking.upc.wizard.line'

    def _validate_scanned_barcode(self):
        try:
            return super()._validate_scanned_barcode()
        except ValidationError:
            if self.env.context.get('systore_operations_mobile') or self.wizard_id.systore_guided_warehouse_id:
                raise ValidationError(_('No coincide UPC/IMEI')) from None
            raise

    systore_requested_qty = fields.Float(string='Piezas solicitadas', readonly=True)
    systore_order_names = fields.Char(string='Número de orden', compute='_compute_guided_order_names')
    systore_scanned_qty = fields.Float(string='Procesadas', compute='_compute_guided_scanned_qty')

    @api.depends('product_id', 'wizard_id.picking_id', 'wizard_id.batch_id')
    def _compute_guided_order_names(self):
        for line in self:
            wizard = line.wizard_id
            pickings = wizard.batch_id.picking_ids if wizard.batch_id else wizard.picking_id
            matching = pickings.filtered(lambda p: line.product_id in p.move_ids.product_id)
            line.systore_order_names = ', '.join(sorted(set(filter(None, matching.mapped('systore_operations_sale_names')))))

    @api.depends('upc_ean', 'serial_imei', 'demand_qty', 'wizard_id.require_serial_imei')
    def _compute_guided_scanned_qty(self):
        for line in self:
            line.systore_scanned_qty = (line.demand_qty if line.upc_ean and
                (not line.wizard_id.require_serial_imei or line.serial_imei) else 0)
