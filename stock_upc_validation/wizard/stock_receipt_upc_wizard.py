from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class StockReceiptUPCWizard(models.TransientModel):
    _name = 'stock.receipt.upc.wizard'
    _description = 'Registrar UPC/EAN en recepción'

    picking_id = fields.Many2one('stock.picking', string='Recepción', required=True, readonly=True)
    origin = fields.Char(string='Documento origen', related='picking_id.origin', readonly=True)
    line_ids = fields.One2many('stock.receipt.upc.wizard.line', 'wizard_id', string='Productos')

    @api.model
    def create_from_picking(self, picking):
        picking.ensure_one()
        values = []
        groups = picking._systore_receipt_validation_groups()
        for group in groups:
            values.append((0, 0, {
                'product_id': group['product_id'],
                'demand_qty': group.get('demand_qty') or 0.0,
                'quantity': group.get('quantity') or group.get('demand_qty') or 0.0,
                # Se deja vacío intencionalmente para obligar al operador a escanear/capturar
                # el UPC/EAN en cada recepción, aunque el producto ya tenga códigos registrados.
                'upc_ean': False,
            }))
        return self.create({
            'picking_id': picking.id,
            'line_ids': values,
        })

    def action_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('No hay productos para validar.'))

        for line in self.line_ids:
            line._validate_quantity()
            line._validate_and_register_barcode()

        self._apply_received_quantities()
        self._assign_origin_as_lot()

        return self.picking_id.with_context(systore_skip_upc_receipt_wizard=True).button_validate()

    def _apply_received_quantities(self):
        """Apply the quantity captured in the wizard to the receipt before validation.

        This allows partial receipts from the UPC wizard itself. Odoo will keep its
        native backorder flow when the captured quantity is lower than demand.
        """
        self.ensure_one()
        picking = self.picking_id
        for wizard_line in self.line_ids:
            remaining = wizard_line.quantity or 0.0
            product_moves = picking.move_ids_without_package.filtered(
                lambda m: m.state not in ('done', 'cancel') and m.product_id.id == wizard_line.product_id.id
            ).sorted(key=lambda m: (getattr(m, 'sequence', 0) or 0, m.id))

            for move in product_moves:
                rounding = move.product_uom.rounding
                move_demand = move.product_uom_qty or 0.0
                qty_for_move = min(remaining, move_demand)
                remaining -= qty_for_move

                # Odoo 18 commonly uses stock.move.quantity as the processed qty.
                # Fallbacks are kept for safer upgrades/customizations.
                if 'quantity' in move._fields:
                    move.quantity = qty_for_move
                elif 'quantity_done' in move._fields:
                    move.quantity_done = qty_for_move
                elif 'qty_done' in move._fields:
                    move.qty_done = qty_for_move

                self._set_move_line_quantity(move, qty_for_move)

                if float_is_zero(remaining, precision_rounding=rounding):
                    remaining = 0.0
                    break

    def _set_move_line_quantity(self, move, qty):
        lines = move.move_line_ids
        if not lines:
            return
        remaining = qty or 0.0
        for idx, ml in enumerate(lines.sorted(key=lambda l: l.id)):
            line_qty = remaining if idx == 0 else 0.0
            if 'quantity' in ml._fields:
                ml.quantity = line_qty
            elif 'qty_done' in ml._fields:
                ml.qty_done = line_qty
            remaining = 0.0

    def _assign_origin_as_lot(self):
        self.ensure_one()
        picking = self.picking_id
        if not picking.picking_type_id.systore_auto_lot_from_origin:
            return

        lot_name = (picking.origin or picking.name or '').strip()
        if not lot_name:
            raise UserError(_('No se encontró documento origen para asignarlo como lote.'))

        StockLot = self.env['stock.lot']
        company = picking.company_id
        for move in picking.move_ids_without_package.filtered(lambda m: m.state not in ('done', 'cancel')):
            product = move.product_id
            if not product or product.tracking == 'none':
                continue
            if product.tracking == 'serial':
                raise UserError(_(
                    'El producto %s usa trazabilidad por número de serie. '
                    'Este módulo asigna automáticamente lotes, no series únicas.'
                ) % product.display_name)

            lot = StockLot.search([
                ('name', '=', lot_name),
                ('product_id', '=', product.id),
                ('company_id', 'in', [company.id, False]),
            ], limit=1)
            if not lot:
                lot = StockLot.create({
                    'name': lot_name,
                    'product_id': product.id,
                    'company_id': company.id,
                })

            for ml in move.move_line_ids:
                if not ml.lot_id:
                    ml.lot_id = lot.id
                if 'lot_name' in ml._fields and not ml.lot_name:
                    ml.lot_name = lot_name


class StockReceiptUPCWizardLine(models.TransientModel):
    _name = 'stock.receipt.upc.wizard.line'
    _description = 'Línea UPC/EAN recepción'

    wizard_id = fields.Many2one('stock.receipt.upc.wizard', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Producto', required=True, readonly=True)
    demand_qty = fields.Float(string='Demanda', readonly=True)
    quantity = fields.Float(string='Cantidad')
    upc_ean = fields.Char(string='UPC/EAN')

    def _validate_quantity(self):
        self.ensure_one()
        rounding = self.product_id.uom_id.rounding
        qty = self.quantity or 0.0
        if float_compare(qty, 0.0, precision_rounding=rounding) < 0:
            raise ValidationError(_('La cantidad recibida de %s no puede ser negativa.') % self.product_id.display_name)
        if float_compare(qty, self.demand_qty or 0.0, precision_rounding=rounding) > 0:
            raise ValidationError(_(
                'La cantidad recibida de %s no puede ser mayor a la demanda (%s).'
            ) % (self.product_id.display_name, self.demand_qty))
        self.quantity = qty

    def _validate_and_register_barcode(self):
        self.ensure_one()
        barcode = (self.upc_ean or '').strip()
        if not barcode:
            raise ValidationError(_('Debe capturar un UPC/EAN para %s.') % self.product_id.display_name)
        self.upc_ean = barcode

        Product = self.env['product.product'].sudo()
        Multi = self.env['product.barcode.multi'].sudo()

        other_primary = Product.search([
            ('barcode', '=', barcode),
            ('id', '!=', self.product_id.id),
            ('active', '=', True),
        ], limit=1)
        if other_primary:
            raise ValidationError(_(
                'El UPC/EAN %s ya está registrado como código principal del producto %s.'
            ) % (barcode, other_primary.display_name))

        other_multi = Multi.search([
            ('name', '=', barcode),
            ('product_id', '!=', self.product_id.id),
            ('product_id.active', '=', True),
        ], limit=1)
        if other_multi:
            raise ValidationError(_(
                'El UPC/EAN %s ya está registrado en el producto %s.'
            ) % (barcode, other_multi.product_id.display_name))

        same_multi = Multi.search([
            ('name', '=', barcode),
            ('product_id', '=', self.product_id.id),
        ], limit=1)
        if same_multi:
            return

        if self.product_id.barcode == barcode:
            # Ya existe como código principal. No se duplica en multi UPC porque el módulo base
            # valida que un mismo producto no repita el código entre barcode y barcode_ids.
            return

        Multi.create({
            'name': barcode,
            'product_id': self.product_id.id,
        })
