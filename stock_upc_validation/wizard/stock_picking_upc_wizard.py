from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError


class StockPickingUPCWizard(models.TransientModel):
    _name = 'stock.picking.upc.wizard'
    _description = 'Validar UPC/EAN en recolección'

    picking_id = fields.Many2one('stock.picking', string='Traslado', readonly=True)
    batch_id = fields.Many2one('stock.picking.batch', string='Batch', readonly=True)
    picking_type_id = fields.Many2one(related='picking_id.picking_type_id', string='Tipo de operación', readonly=True)
    require_tracking_on_pack = fields.Boolean(related='picking_id.systore_require_tracking_on_pack', readonly=True)
    require_serial_imei = fields.Boolean(related='picking_id.systore_require_tracking_on_pack', readonly=True)
    tracking_ref = fields.Char(string='Número de guía')
    line_ids = fields.One2many('stock.picking.upc.wizard.line', 'wizard_id', string='Productos a validar')

    @api.model
    def create_from_picking(self, picking):
        picking.ensure_one()
        values = []

        # PACK: validar pieza por pieza para capturar NS/IMEI individual.
        if picking.systore_require_tracking_on_pack:
            scan_count_by_product = {}
            moves = picking.move_ids_without_package.filtered(
                lambda m: m.state not in ('done', 'cancel')
                and m.product_id
                and m.product_id.type in ('product', 'consu')
            )
            for move in moves.sorted(key=lambda m: (getattr(m, 'sequence', 0) or 0, m.id)):
                qty = int(round(picking._systore_move_effective_qty(move) or 0.0))
                if qty <= 0:
                    qty = int(round(move.product_uom_qty or 0.0))
                for _idx in range(max(qty, 1)):
                    scan_count_by_product[move.product_id.id] = scan_count_by_product.get(move.product_id.id, 0) + 1
                    values.append((0, 0, {
                        'product_id': move.product_id.id,
                        'lot_id': False,
                        'scan_no': scan_count_by_product[move.product_id.id],
                        'demand_qty': 1.0,
                        'upc_ean': False,
                        'serial_imei': False,
                    }))
        else:
            # PICK / recolección: validar de forma masiva por producto.
            # Una línea escaneada representa toda la demanda del producto, aunque venga de varios lotes nativos.
            grouped = picking._systore_pick_validation_groups()
            seq = 0
            for group in grouped:
                seq += 1
                values.append((0, 0, {
                    'product_id': group['product_id'],
                    'lot_id': group.get('lot_id') or False,
                    'scan_no': seq,
                    'demand_qty': group.get('demand_qty') or 0.0,
                    'upc_ean': False,
                    'serial_imei': False,
                }))

        return self.create({
            'picking_id': picking.id,
            'line_ids': values,
        })

    @api.model
    def create_from_batch(self, batch):
        batch.ensure_one()
        values = []
        groups = {}
        order = []

        pickings = batch.picking_ids.filtered(lambda p: p._systore_needs_upc_picking_wizard())
        for picking in pickings.sorted(key=lambda p: (p.name or '', p.id)):
            for group in picking._systore_pick_validation_groups():
                product_id = group['product_id']
                if product_id not in groups:
                    groups[product_id] = {
                        'product_id': product_id,
                        'lot_id': False,
                        'demand_qty': 0.0,
                    }
                    order.append(product_id)
                groups[product_id]['demand_qty'] += group.get('demand_qty') or 0.0

        seq = 0
        for product_id in order:
            seq += 1
            group = groups[product_id]
            values.append((0, 0, {
                'product_id': group['product_id'],
                'lot_id': False,
                'scan_no': seq,
                'demand_qty': group.get('demand_qty') or 0.0,
                'upc_ean': False,
                'serial_imei': False,
            }))

        return self.create({
            'batch_id': batch.id,
            'line_ids': values,
        })

    def _target_pickings(self):
        self.ensure_one()
        if self.batch_id:
            return self.batch_id.picking_ids.filtered(lambda p: p._systore_needs_upc_picking_wizard())
        return self.picking_id

    def action_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('No hay productos para validar.'))
        vals = {'systore_upc_picking_validated': True}
        if self.require_tracking_on_pack:
            tracking = (self.tracking_ref or '').strip()
            if not tracking:
                raise ValidationError(_('Debe capturar el número de guía antes de validar el empaque %s.') % self.picking_id.display_name)
            vals['carrier_tracking_ref'] = tracking

        for line in self.line_ids:
            line._validate_scanned_barcode()
            if self.require_serial_imei:
                line._validate_serial_imei()
        if self.require_serial_imei:
            self._create_additional_serials()
        if self.batch_id:
            pickings = self._target_pickings()
            if not pickings:
                raise UserError(_('No hay traslados pendientes para validar en este batch.'))
            pickings.sudo().write(vals)
            batch = self.batch_id.with_context(
                systore_skip_upc_batch_wizard=True,
                systore_skip_upc_picking_wizard=True,
            )
            if hasattr(batch, 'button_validate'):
                return batch.button_validate()
            return batch.action_done()

        self.picking_id.sudo().write(vals)
        return self.picking_id.with_context(systore_skip_upc_picking_wizard=True).button_validate()

    def _create_additional_serials(self):
        self.ensure_one()
        Serial = self.env['stock.move.line.serial'].sudo()
        to_create = []
        assigned_count_by_ml = {}

        # Keep assignment deterministic: each NS/IMEI is linked to a move line
        # of the expected product in the same picking. Multiple serials can be
        # registered on the same move line when quantities are grouped.
        for line in self.line_ids.sorted(key=lambda l: (l.product_id.display_name or '', l.scan_no, l.id)):
            serial = (line.serial_imei or '').strip()
            if not serial:
                continue

            move_line = line._find_target_move_line(assigned_count_by_ml)
            if not move_line:
                raise UserError(_(
                    'No se encontró una línea de movimiento para registrar el NS/IMEI %s del producto %s.'
                ) % (serial, line.product_id.display_name))

            existing_same_picking = Serial.search([
                ('picking_id', '=', self.picking_id.id),
                ('name', '=', serial),
            ], limit=1)
            if existing_same_picking:
                raise ValidationError(_('El NS/IMEI %s ya está registrado en esta operación.') % serial)

            to_create.append({
                'name': serial,
                'move_line_id': move_line.id,
            })
            assigned_count_by_ml[move_line.id] = assigned_count_by_ml.get(move_line.id, 0) + 1

        if to_create:
            Serial.create(to_create)


class StockPickingUPCWizardLine(models.TransientModel):
    _name = 'stock.picking.upc.wizard.line'
    _description = 'Línea validación UPC/EAN recolección'

    wizard_id = fields.Many2one('stock.picking.upc.wizard', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Producto esperado', required=True, readonly=True)
    lot_id = fields.Many2one('stock.lot', string='Lote', readonly=True)
    scan_no = fields.Integer(string='#', readonly=True)
    demand_qty = fields.Float(string='Demanda', readonly=True)
    upc_ean = fields.Char(string='UPC/EAN escaneado')
    serial_imei = fields.Char(string='NS/IMEI')

    def _validate_scanned_barcode(self):
        self.ensure_one()
        barcode = (self.upc_ean or '').strip()
        if not barcode:
            raise ValidationError(_('Debe escanear/capturar un UPC/EAN para %s.') % self.product_id.display_name)
        self.upc_ean = barcode

        product = self.product_id.sudo()
        if product.barcode == barcode:
            return True

        multi = self.env['product.barcode.multi'].sudo().search([
            ('name', '=', barcode),
            ('product_id', '=', product.id),
        ], limit=1)
        if multi:
            return True

        other_primary = self.env['product.product'].sudo().search([
            ('barcode', '=', barcode),
            ('active', '=', True),
        ], limit=1)
        if other_primary:
            raise ValidationError(_(
                'El UPC/EAN %s pertenece al producto %s, pero el traslado espera %s.'
            ) % (barcode, other_primary.display_name, product.display_name))

        other_multi = self.env['product.barcode.multi'].sudo().search([
            ('name', '=', barcode),
            ('product_id.active', '=', True),
        ], limit=1)
        if other_multi:
            raise ValidationError(_(
                'El UPC/EAN %s pertenece al producto %s, pero el traslado espera %s.'
            ) % (barcode, other_multi.product_id.display_name, product.display_name))

        raise ValidationError(_(
            'El UPC/EAN %s no está registrado para el producto %s. '
            'Registre primero el código en recepción o en UPC/EAN múltiples.'
        ) % (barcode, product.display_name))


    def _validate_serial_imei(self):
        self.ensure_one()
        serial = (self.serial_imei or '').strip()
        if not serial:
            raise ValidationError(_('Debe capturar el NS/IMEI para %s.') % self.product_id.display_name)
        self.serial_imei = serial
        return True

    def _find_target_move_line(self, assigned_count_by_ml=None):
        self.ensure_one()
        assigned_count_by_ml = assigned_count_by_ml or {}
        lines = self.wizard_id.picking_id.move_line_ids.filtered(lambda ml: ml.product_id.id == self.product_id.id)
        if not lines:
            # In some flows move_line_ids may not be fully split yet; fallback to move lines from moves.
            lines = self.wizard_id.picking_id.move_ids_without_package.mapped('move_line_ids').filtered(
                lambda ml: ml.product_id.id == self.product_id.id
            )

        def _target_qty(ml):
            qty = 0.0
            if 'quantity' in ml._fields:
                qty = ml.quantity or 0.0
            elif 'qty_done' in ml._fields:
                qty = ml.qty_done or 0.0
            if not qty:
                qty = getattr(ml, 'reserved_uom_qty', 0.0) or getattr(ml, 'reserved_quantity', 0.0) or 0.0
            if not qty and ml.move_id:
                qty = ml.move_id.product_uom_qty or 0.0
            return int(round(qty or 0.0))

        # Prefer a line that still has available serial capacity according to its quantity.
        for ml in lines.sorted(key=lambda m: (getattr(m, 'sequence', 0) or 0, m.id)):
            target = _target_qty(ml) or 1
            current_existing = len(ml.serial_captured_ids)
            current_new = assigned_count_by_ml.get(ml.id, 0)
            if current_existing + current_new < target:
                return ml

        # If all lines are already at target, still attach to the first matching line instead of losing the capture.
        return lines[:1]
