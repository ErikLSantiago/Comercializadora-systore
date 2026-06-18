from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError


class StockPickingUPCWizard(models.TransientModel):
    _name = 'stock.picking.upc.wizard'
    _description = 'Validar UPC/EAN en recolección'

    picking_id = fields.Many2one('stock.picking', string='Traslado', required=True, readonly=True)
    picking_type_id = fields.Many2one(related='picking_id.picking_type_id', string='Tipo de operación', readonly=True)
    require_tracking_on_pack = fields.Boolean(related='picking_id.systore_require_tracking_on_pack', readonly=True)
    tracking_ref = fields.Char(string='Número de guía')
    line_ids = fields.One2many('stock.picking.upc.wizard.line', 'wizard_id', string='Productos a validar')

    @api.model
    def create_from_picking(self, picking):
        picking.ensure_one()
        scans_per_product = max(picking.picking_type_id.systore_upc_validation_per_product or 1, 1)
        values = []
        for product in picking._systore_picking_products_to_validate():
            for scan_no in range(scans_per_product):
                values.append((0, 0, {
                    'product_id': product.id,
                    'scan_no': scan_no + 1,
                    'upc_ean': False,
                    'serial_imei': False,
                }))
        return self.create({
            'picking_id': picking.id,
            'line_ids': values,
        })

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
            line._validate_serial_imei()
        self._create_additional_serials()
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
    scan_no = fields.Integer(string='#', readonly=True)
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
