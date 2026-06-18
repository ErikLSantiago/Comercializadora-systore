from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


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
        for product in picking._systore_receipt_products_to_validate():
            values.append((0, 0, {
                'product_id': product.id,
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
            line._validate_and_register_barcode()

        self._assign_origin_as_lot()

        return self.picking_id.with_context(systore_skip_upc_receipt_wizard=True).button_validate()

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
    upc_ean = fields.Char(string='UPC/EAN')

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
