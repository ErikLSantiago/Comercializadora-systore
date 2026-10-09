from collections import Counter

from odoo import _, Command, api, fields, models
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_compare, float_is_zero


class StockPickingUPCWizard(models.TransientModel):
    _name = 'stock.picking.upc.wizard'
    _description = 'Validar UPC/EAN en recolección'

    picking_id = fields.Many2one('stock.picking', string='Traslado', readonly=True)
    batch_id = fields.Many2one('stock.picking.batch', string='Batch', readonly=True)
    picking_type_id = fields.Many2one(related='picking_id.picking_type_id', string='Tipo de operación', readonly=True)
    require_tracking_on_pack = fields.Boolean(compute='_compute_pack_requirements', readonly=True)
    require_serial_imei = fields.Boolean(compute='_compute_pack_requirements', readonly=True)
    mass_capture_available = fields.Boolean(compute='_compute_pack_requirements', readonly=True)
    capture_massive = fields.Boolean(string='Captura masiva')
    tracking_ref = fields.Char(string='Número de guía')
    skip_tracking_ref = fields.Boolean(string='No asignar número de guía')
    line_ids = fields.One2many('stock.picking.upc.wizard.line', 'wizard_id', string='Productos a validar')

    @api.depends('picking_id', 'picking_id.picking_type_id')
    def _compute_pack_requirements(self):
        for wizard in self:
            full_pack = bool(wizard.picking_id and wizard.picking_id._systore_requires_full_pack_validation())
            wizard.require_tracking_on_pack = full_pack
            wizard.require_serial_imei = full_pack
            wizard.mass_capture_available = full_pack

    @api.onchange('capture_massive')
    def _onchange_capture_massive(self):
        for wizard in self:
            if not wizard.picking_id or not wizard.mass_capture_available:
                wizard.capture_massive = False
                continue
            values = wizard._prepare_picking_line_values(wizard.picking_id, wizard.capture_massive)
            wizard._validate_prepared_line_values(wizard.picking_id, values)
            wizard.line_ids = [Command.clear()] + [Command.create(value) for value in values]

    @api.model
    def _validate_prepared_line_values(self, picking, values):
        """Fail early if a generated wizard row is not tied to a stock product."""
        picking.ensure_one()
        active_moves = picking.move_ids_without_package.filtered(
            lambda move: move.state not in ('done', 'cancel')
        )
        inconsistent_moves = active_moves.filtered(lambda move: not move.product_id)
        if inconsistent_moves:
            move_names = ', '.join(inconsistent_moves.mapped('display_name')) or _('sin referencia')
            raise UserError(_(
                'No se puede abrir la validación UPC/EAN del traslado %(picking)s porque '
                'los siguientes movimientos no tienen producto: %(moves)s. '
                'Corrija los movimientos de inventario e intente nuevamente.'
            ) % {
                'picking': picking.display_name,
                'moves': move_names,
            })

        valid_product_ids = set(active_moves.mapped('product_id').ids)
        for index, value in enumerate(values, start=1):
            product_id = value.get('product_id')
            if not product_id or product_id not in valid_product_ids:
                raise UserError(_(
                    'No se pudo construir la línea %(line)s de validación UPC/EAN para '
                    'el traslado %(picking)s porque no tiene un producto válido asociado. '
                    'Revise los movimientos de inventario e intente nuevamente.'
                ) % {
                    'line': index,
                    'picking': picking.display_name,
                })
        return True

    @api.model
    def _prepare_picking_line_values(self, picking, capture_massive=False):
        values = []
        if picking._systore_requires_full_pack_validation() and not capture_massive:
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
                    values.append({
                        'product_id': move.product_id.id,
                        'lot_id': False,
                        'scan_no': scan_count_by_product[move.product_id.id],
                        'demand_qty': 1.0,
                        'processed_qty': 1.0,
                        'upc_ean': False,
                        'serial_imei': False,
                        'skip_upc_validation': False,
                    })
            return values

        # La captura masiva y la recolección normal usan una línea por producto.
        for seq, group in enumerate(picking._systore_pick_validation_groups(), start=1):
            demand_qty = group.get('demand_qty') or 0.0
            values.append({
                'product_id': group['product_id'],
                'lot_id': group.get('lot_id') or False,
                'scan_no': seq,
                'demand_qty': demand_qty,
                'processed_qty': demand_qty,
                'upc_ean': False,
                'serial_imei': False,
                'skip_upc_validation': False,
            })
        return values

    @api.model
    def create_from_picking(self, picking):
        picking.ensure_one()
        line_values = self._prepare_picking_line_values(picking)
        self._validate_prepared_line_values(picking, line_values)
        values = [Command.create(value) for value in line_values]

        return self.create({
            'picking_id': picking.id,
            'capture_massive': False,
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
            picking_groups = picking._systore_pick_validation_groups()
            self._validate_prepared_line_values(picking, picking_groups)
            for group in picking_groups:
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
                'processed_qty': group.get('demand_qty') or 0.0,
                'upc_ean': False,
                'serial_imei': False,
                'skip_upc_validation': False,
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
        self._validate_header_inputs()

        if self.capture_massive and self.require_serial_imei:
            serial_wizard = self.env['stock.picking.mass.serial.wizard'].create_from_upc_wizard(self)
            if serial_wizard.line_ids:
                return {
                    'name': _('Capturar múltiples NS/IMEI'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'stock.picking.mass.serial.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'res_id': serial_wizard.id,
                }
            # Todos los productos fueron marcados sin UPC/EAN; tampoco requieren NS/IMEI.
            return self._finalize_validation()

        return self._finalize_validation()

    def _validate_header_inputs(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('No hay productos para validar.'))

        if self.require_tracking_on_pack:
            tracking = (self.tracking_ref or '').strip()
            if not tracking and not self.skip_tracking_ref:
                raise ValidationError(_('Debe capturar el número de guía antes de validar el empaque %s.') % self.picking_id.display_name)
            self.tracking_ref = tracking or False

        for line in self.line_ids:
            line._validate_processed_qty(self.capture_massive)
            line._validate_scanned_barcode()
            if self.require_serial_imei and not self.capture_massive:
                line._validate_serial_imei()
        return True

    def _finalize_validation(self, mass_serial_lines=None):
        self.ensure_one()
        self._validate_header_inputs()
        vals = {'systore_upc_picking_validated': True}
        if self.require_tracking_on_pack and not self.skip_tracking_ref:
            vals['carrier_tracking_ref'] = (self.tracking_ref or '').strip()

        self._post_skip_upc_message()
        self._post_skip_tracking_message()
        if self.require_serial_imei:
            self._create_additional_serials(mass_serial_lines=mass_serial_lines)

        # Permite procesos parciales desde el wizard: las líneas eliminadas no se procesan.
        # Se ajustan las cantidades del traslado antes de llamar button_validate para que
        # Odoo conserve su flujo nativo de backorder cuando aplique.
        self._apply_validated_quantities()

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
        return self.picking_id.with_context(
            systore_skip_upc_picking_wizard=True,
            systore_skip_pack_tracking_wizard=bool(self.skip_tracking_ref),
        ).button_validate()

    def _post_skip_tracking_message(self):
        self.ensure_one()
        if not self.require_tracking_on_pack or not self.skip_tracking_ref:
            return
        body = _(
            '<b>Número de guía omitido</b><br/>'
            'El usuario <b>%s</b> validó la operación sin asignar número de guía.'
        ) % self.env.user.display_name
        self.picking_id.sudo().message_post(body=body)

    def _post_skip_upc_message(self):
        self.ensure_one()
        skipped_lines = self.line_ids.filtered('skip_upc_validation')
        if not skipped_lines:
            return

        product_names = sorted(set(skipped_lines.mapped('product_id.display_name')))
        products_html = ''.join('<li>%s</li>' % name for name in product_names)
        body = _(
            '<b>Validación UPC/EAN omitida</b><br/>'
            'El usuario <b>%s</b> omitió la validación UPC/EAN para los siguientes productos:<ul>%s</ul>'
            'Motivo: <b>El producto no cuenta con UPC/EAN.</b>'
        ) % (self.env.user.display_name, products_html)

        if self.batch_id:
            self.batch_id.sudo().message_post(body=body)
            skipped_product_ids = set(skipped_lines.mapped('product_id').ids)
            for picking in self._target_pickings():
                picking_product_ids = set(picking.move_ids_without_package.mapped('product_id').ids)
                matched_product_ids = skipped_product_ids.intersection(picking_product_ids)
                if not matched_product_ids:
                    continue
                matched_names = self.env['product.product'].browse(list(matched_product_ids)).mapped('display_name')
                matched_html = ''.join('<li>%s</li>' % name for name in sorted(matched_names))
                picking_body = _(
                    '<b>Validación UPC/EAN omitida desde Batch Picking</b><br/>'
                    'El usuario <b>%s</b> omitió la validación UPC/EAN para los siguientes productos:<ul>%s</ul>'
                    'Motivo: <b>El producto no cuenta con UPC/EAN.</b>'
                ) % (self.env.user.display_name, matched_html)
                picking.sudo().message_post(body=picking_body)
            return

        self.picking_id.sudo().message_post(body=body)

    def _apply_validated_quantities(self):
        """Apply only the quantities represented by the remaining wizard lines.

        If the operator deletes one or more lines from the wizard, those products/pieces
        are treated as not processed in the current validation. Odoo then decides whether
        to create a backorder using its native flow.
        """
        self.ensure_one()

        def _qty_by_product(lines):
            result = {}
            for line in lines:
                qty = line.processed_qty if self.capture_massive else line.demand_qty
                result[line.product_id.id] = result.get(line.product_id.id, 0.0) + (qty or 0.0)
            return result

        if self.batch_id:
            # Batch wizard lines are grouped by product. Apply available target qty
            # across the pending pickings deterministically.
            remaining_by_product = _qty_by_product(self.line_ids)
            for picking in self._target_pickings().sorted(key=lambda p: (p.name or '', p.id)):
                self._apply_quantities_to_picking(picking, remaining_by_product)
            return

        self._apply_quantities_to_picking(self.picking_id, _qty_by_product(self.line_ids))

    def _apply_quantities_to_picking(self, picking, remaining_by_product):
        for move in picking.move_ids_without_package.filtered(lambda m: m.state not in ('done', 'cancel')):
            product_id = move.product_id.id
            remaining = remaining_by_product.get(product_id, 0.0)
            move_demand = move.product_uom_qty or 0.0
            qty_for_move = min(remaining, move_demand)
            remaining_by_product[product_id] = max(remaining - qty_for_move, 0.0)

            if 'quantity' in move._fields:
                move.quantity = qty_for_move
            elif 'quantity_done' in move._fields:
                move.quantity_done = qty_for_move
            elif 'qty_done' in move._fields:
                move.qty_done = qty_for_move

            self._set_move_line_quantity(move, qty_for_move)

    def _set_move_line_quantity(self, move, qty):
        lines = move.move_line_ids
        if not lines:
            return
        remaining = qty or 0.0
        for ml in lines.sorted(key=lambda l: (getattr(l, 'sequence', 0) or 0, l.id)):
            current_capacity = 0.0
            if 'quantity' in ml._fields:
                current_capacity = ml.quantity or 0.0
            elif 'reserved_uom_qty' in ml._fields:
                current_capacity = ml.reserved_uom_qty or 0.0
            elif 'reserved_quantity' in ml._fields:
                current_capacity = ml.reserved_quantity or 0.0
            elif 'product_uom_qty' in ml._fields:
                current_capacity = ml.product_uom_qty or 0.0
            if not current_capacity:
                current_capacity = move.product_uom_qty or 0.0

            line_qty = min(remaining, current_capacity) if remaining else 0.0
            if 'quantity' in ml._fields:
                ml.quantity = line_qty
            elif 'qty_done' in ml._fields:
                ml.qty_done = line_qty
            remaining = max(remaining - line_qty, 0.0)

    def _create_additional_serials(self, mass_serial_lines=None):
        self.ensure_one()
        Serial = self.env['stock.move.line.serial'].sudo()
        to_create = []
        assigned_count_by_ml = {}
        entries = []

        if mass_serial_lines is not None:
            for serial_line in mass_serial_lines.sorted(key=lambda l: (l.product_id.display_name or '', l.scan_no, l.id)):
                source_line = self.line_ids.filtered(lambda l: l.product_id == serial_line.product_id)[:1]
                entries.append((source_line, (serial_line.serial_imei or '').strip()))
        else:
            for line in self.line_ids.sorted(key=lambda l: (l.product_id.display_name or '', l.scan_no, l.id)):
                if line.skip_upc_validation:
                    continue
                entries.append((line, (line.serial_imei or '').strip()))

        serial_values = [serial for _line, serial in entries if serial]
        duplicates = sorted(name for name, count in Counter(serial_values).items() if count > 1)
        if duplicates:
            raise ValidationError(_(
                'Los siguientes NS/IMEI están duplicados en la captura: %s'
            ) % ', '.join(duplicates))

        existing = Serial.search([('name', 'in', serial_values)]) if serial_values else Serial.browse()
        if existing:
            raise ValidationError(_(
                'Los siguientes NS/IMEI ya están registrados: %s'
            ) % ', '.join(sorted(set(existing.mapped('name')))))

        # Keep assignment deterministic: each NS/IMEI is linked to a move line
        # of the expected product in the same picking. Multiple serials can be
        # registered on the same move line when quantities are grouped.
        for line, serial in entries:
            if not serial:
                continue

            move_line = line._find_target_move_line(assigned_count_by_ml)
            if not move_line:
                raise UserError(_(
                    'No se encontró una línea de movimiento para registrar el NS/IMEI %s del producto %s.'
                ) % (serial, line.product_id.display_name))

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
    processed_qty = fields.Float(string='Piezas a procesar')
    upc_ean = fields.Char(string='UPC/EAN escaneado')
    serial_imei = fields.Char(string='NS/IMEI')
    skip_upc_validation = fields.Boolean(string='El producto no cuenta con UPC/EAN')

    @api.model_create_multi
    def create(self, vals_list):
        """Avoid the database-level required-field error and explain the bad row."""
        for values in vals_list:
            if not values.get('product_id'):
                raise ValidationError(_(
                    'No se puede crear una línea de validación UPC/EAN sin producto. '
                    'Cierre el asistente, revise los movimientos del traslado y vuelva a intentarlo.'
                ))
        return super().create(vals_list)

    def _validate_processed_qty(self, capture_massive=False):
        self.ensure_one()
        if not capture_massive:
            return True
        qty = self.processed_qty or 0.0
        rounding = self.product_id.uom_id.rounding or 0.00001
        if float_compare(qty, 0.0, precision_rounding=rounding) <= 0:
            raise ValidationError(_(
                'Las piezas a procesar de %s deben ser mayores que cero.'
            ) % self.product_id.display_name)
        if float_compare(qty, self.demand_qty, precision_rounding=rounding) > 0:
            raise ValidationError(_(
                'No puede procesar %(qty)s piezas de %(product)s; sólo hay %(available)s disponibles.'
            ) % {
                'qty': qty,
                'product': self.product_id.display_name,
                'available': self.demand_qty,
            })
        if not float_is_zero(qty - round(qty), precision_rounding=0.00001):
            raise ValidationError(_(
                'La captura de NS/IMEI requiere una cantidad entera de piezas para %s.'
            ) % self.product_id.display_name)
        self.processed_qty = round(qty)
        return True

    def _validate_scanned_barcode(self):
        self.ensure_one()
        if self.skip_upc_validation:
            self.upc_ean = False
            return True

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
        if self.skip_upc_validation:
            self.serial_imei = False
            return True
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


class StockPickingMassSerialWizard(models.TransientModel):
    _name = 'stock.picking.mass.serial.wizard'
    _description = 'Captura masiva de NS/IMEI'

    upc_wizard_id = fields.Many2one(
        'stock.picking.upc.wizard',
        string='Validación UPC/EAN',
        required=True,
        readonly=True,
        ondelete='cascade',
    )
    picking_id = fields.Many2one(
        related='upc_wizard_id.picking_id',
        string='Traslado',
        readonly=True,
    )
    line_ids = fields.One2many(
        'stock.picking.mass.serial.wizard.line',
        'wizard_id',
        string='NS/IMEI',
    )

    @api.model
    def create_from_upc_wizard(self, upc_wizard):
        upc_wizard.ensure_one()
        values = []
        for upc_line in upc_wizard.line_ids.sorted(key=lambda l: (l.scan_no, l.id)):
            if upc_line.skip_upc_validation:
                continue
            qty = int(round(upc_line.processed_qty or 0.0))
            for scan_no in range(1, qty + 1):
                values.append(Command.create({
                    'product_id': upc_line.product_id.id,
                    'scan_no': scan_no,
                    'serial_imei': False,
                }))
        return self.create({
            'upc_wizard_id': upc_wizard.id,
            'line_ids': values,
        })

    def action_confirm(self):
        self.ensure_one()
        expected_by_product = {
            line.product_id.id: int(round(line.processed_qty or 0.0))
            for line in self.upc_wizard_id.line_ids
            if not line.skip_upc_validation
        }
        actual_by_product = Counter(self.line_ids.mapped('product_id').ids)
        if actual_by_product != Counter(expected_by_product):
            raise ValidationError(_(
                'La cantidad de NS/IMEI debe coincidir exactamente con las piezas a procesar de cada producto.'
            ))

        serials = []
        for line in self.line_ids:
            serial = (line.serial_imei or '').strip()
            if not serial:
                raise ValidationError(_(
                    'Debe capturar todos los NS/IMEI. Falta el número %(number)s de %(product)s.'
                ) % {
                    'number': line.scan_no,
                    'product': line.product_id.display_name,
                })
            line.serial_imei = serial
            serials.append(serial)

        duplicates = sorted(name for name, count in Counter(serials).items() if count > 1)
        if duplicates:
            raise ValidationError(_(
                'Los siguientes NS/IMEI están duplicados en la captura: %s'
            ) % ', '.join(duplicates))

        return self.upc_wizard_id._finalize_validation(mass_serial_lines=self.line_ids)


class StockPickingMassSerialWizardLine(models.TransientModel):
    _name = 'stock.picking.mass.serial.wizard.line'
    _description = 'Línea de captura masiva de NS/IMEI'
    _order = 'product_id, scan_no, id'

    wizard_id = fields.Many2one(
        'stock.picking.mass.serial.wizard',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        readonly=True,
    )
    scan_no = fields.Integer(string='#', readonly=True)
    serial_imei = fields.Char(string='NS/IMEI')
