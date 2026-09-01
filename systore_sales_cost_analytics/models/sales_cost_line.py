# -*- coding: utf-8 -*-
import re
import unicodedata
from collections import defaultdict

from odoo import api, fields, models, _


class SystoreSalesCostLine(models.Model):
    _name = 'systore.sales.cost.line'
    _description = 'Analítica consolidada de venta, factura, lote y costo'
    _order = 'invoice_date desc, invoice_id desc, product_id, lot_name'
    _rec_name = 'display_name'

    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)

    invoice_date = fields.Date(string='Fecha factura', index=True, readonly=True)
    invoice_id = fields.Many2one('account.move', string='Factura', index=True, readonly=True, ondelete='cascade')
    invoice_line_id = fields.Many2one('account.move.line', string='Línea factura', index=True, readonly=True, ondelete='cascade')
    move_name = fields.Char(string='Número factura', index=True, readonly=True)
    invoice_origin = fields.Char(string='Orden de venta factura (Origen)', index=True, readonly=True)
    sale_origin = fields.Char(string='Origen movimiento', index=True, readonly=True)
    order_base = fields.Char(string='Orden base', index=True, readonly=True)
    ref = fields.Char(string='Referencia', readonly=True)

    account_id = fields.Many2one('account.account', string='Cuenta contable', index=True, readonly=True)
    account_analytics_type = fields.Selection(related='account_id.systore_analytics_type', string='Tipo cuenta', store=True, readonly=True)
    is_transit_return = fields.Boolean(string='Devolución en tránsito', compute='_compute_is_transit_return', store=True)

    partner_id = fields.Many2one('res.partner', string='Cliente de factura', index=True, readonly=True)
    customer_contact_id = fields.Many2one('res.partner', string='Contacto del cliente', index=True, readonly=True)
    product_id = fields.Many2one('product.product', string='Producto', index=True, readonly=True)
    sku = fields.Char(string='SKU', index=True, readonly=True)
    product_name = fields.Char(string='Nombre del producto (Producto/Nombre)', readonly=True)

    invoice_quantity = fields.Float(string='Cantidad facturada', readonly=True)
    matched_quantity = fields.Float(string='Piezas facturadas', readonly=True)
    invoice_credit = fields.Monetary(string='Crédito', currency_field='company_currency_id', readonly=True)
    invoice_debit = fields.Monetary(string='Débito', currency_field='company_currency_id', readonly=True)
    accounting_amount = fields.Monetary(string='Venta contable', currency_field='company_currency_id', readonly=True,
        help='Crédito menos débito de la línea contable.')
    allocated_sale_amount = fields.Monetary(string='Venta asignada', currency_field='company_currency_id', readonly=True,
        help='Venta contable distribuida proporcionalmente entre los lotes conciliados.')

    sale_order_id = fields.Many2one('sale.order', string='Pedido de venta', index=True, readonly=True)
    salesperson_id = fields.Many2one('res.users', string='Vendedor', index=True, readonly=True)
    analytic_role = fields.Selection([('sale', 'Venta bruta'), ('transit_return', 'Devolución en tránsito')], string='Rol analítico', default='sale', index=True, readonly=True)
    sales_channel = fields.Char(string='Canal de venta', compute='_compute_sales_channel', store=True, index=True, readonly=True)
    transit_account_id = fields.Many2one('account.account', string='Cuenta Tránsito contraparte', compute='_compute_sale_state', store=True, readonly=True, index=True)
    marketplace_order_number = fields.Char(string='Número de orden mkp', index=True, readonly=True)
    sale_state = fields.Selection([
        ('sale', 'Venta'),
        ('return', 'Devolución'),
    ], string='Estado de venta', compute='_compute_sale_state', store=True, index=True, readonly=True)
    sale_order_line_id = fields.Many2one('sale.order.line', string='Línea de venta', index=True, readonly=True)
    stock_move_line_id = fields.Many2one('stock.move.line', string='Movimiento de stock', index=True, readonly=True)
    picking_id = fields.Many2one('stock.picking', string='Transferencia', index=True, readonly=True)
    movement_date = fields.Datetime(string='Fecha movimiento', index=True, readonly=True)
    location_id = fields.Many2one('stock.location', string='Desde', readonly=True)
    location_dest_id = fields.Many2one('stock.location', string='A', readonly=True)
    physical_move_type = fields.Selection([
        ('sale', 'Salida a cliente'),
        ('return', 'Retorno desde cliente'),
        ('other', 'Otro'),
        ('none', 'Sin movimiento'),
    ], string='Movimiento físico', index=True, readonly=True)

    lot_id = fields.Many2one('stock.lot', string='Lote', index=True, readonly=True)
    lot_name = fields.Char(string='Lote / referencia OC', index=True, readonly=True)
    invoice_match_code = fields.Char(string='Code Orden', index=True, readonly=True,
        help='Orden base + SKU. Llave de auditoría/fallback para factura contra movimiento.')
    cost_match_code = fields.Char(string='Code Cost', index=True, readonly=True,
        help='Lote + SKU. Llave de auditoría/fallback para movimiento contra compra.')

    purchase_order_id = fields.Many2one('purchase.order', string='Orden de compra', index=True, readonly=True)
    purchase_order_line_id = fields.Many2one('purchase.order.line', string='Línea OC', index=True, readonly=True)
    vendor_id = fields.Many2one('res.partner', string='Proveedor', index=True, readonly=True)
    purchase_date = fields.Datetime(string='Fecha OC', index=True, readonly=True)
    purchase_currency_id = fields.Many2one('res.currency', string='Moneda OC', readonly=True)
    purchase_unit_cost = fields.Monetary(string='Costo unitario OC', currency_field='purchase_currency_id', readonly=True)
    unit_cost_company = fields.Monetary(string='Costo unitario', currency_field='company_currency_id', readonly=True)
    allocated_cost = fields.Monetary(string='Costo asignado', currency_field='company_currency_id', readonly=True,
        help='Campo técnico conservado por compatibilidad. Equivale al costo total de la cantidad conciliada.')
    total_cost = fields.Monetary(string='Costo total', currency_field='company_currency_id', compute='_compute_profit', store=True)
    unit_sale_price = fields.Monetary(string='Precio de venta unitario', currency_field='company_currency_id', compute='_compute_profit', store=True)
    gross_profit = fields.Monetary(string='Utilidad', currency_field='company_currency_id', compute='_compute_profit', store=True,
        help='Utilidad unitaria: Precio de venta unitario menos Costo unitario.')
    total_profit = fields.Monetary(string='Utilidad total', currency_field='company_currency_id', compute='_compute_profit', store=True)
    gross_margin = fields.Float(string='Margen %', compute='_compute_profit', store=True, group_operator='avg')

    reconciliation_state = fields.Selection([
        ('ok', 'Cuadre correcto'),
        ('no_stock', 'Sin movimiento/lote'),
        ('no_purchase', 'Sin compra'),
        ('no_cost', 'Sin costo'),
        ('qty_diff', 'Diferencia de cantidad'),
    ], string='Estado de cuadre', index=True, readonly=True)
    note = fields.Char(string='Observación', readonly=True)

    display_name = fields.Char(compute='_compute_display_name')

    _sql_constraints = [
        ('invoice_stock_unique', 'unique(invoice_line_id, stock_move_line_id, lot_id)',
         'La combinación de línea de factura y movimiento/lote ya existe.'),
    ]

    @api.model
    def _systore_normalize_text(self, value):
        value = (value or '').strip().lower()
        return ''.join(
            char for char in unicodedata.normalize('NFD', value)
            if unicodedata.category(char) != 'Mn'
        )

    @api.model
    def _systore_account_sale_state(self, account):
        """Clasifica Venta/Devolución usando la cuenta contable de CxC.

        La configuración explícita tiene prioridad. Como respaldo operativo, una cuenta
        cuyo nombre contenga "Tránsito/Transito" se considera Devolución y una cuenta
        cuyo nombre contenga "Clientes" se considera Venta. Esto replica la regla
        usada por Systore para Walmart, Mercado Libre y otros marketplaces.
        """
        if not account:
            return 'sale'
        if account.systore_analytics_type == 'transit_return':
            return 'return'
        if account.systore_analytics_type == 'sale':
            return 'sale'
        normalized = self._systore_normalize_text(account.name)
        if 'transito' in normalized:
            return 'return'
        if 'clientes' in normalized:
            return 'sale'
        return 'sale'

    @api.model
    def _systore_transit_counterpart(self, move):
        """Devuelve la cuenta 106.xx de Tránsito presente como contrapartida del asiento.

        En la operación de Systore, una factura cuya póliza contiene una cuenta 106.xx
        llamada Tránsito se considera devolución, aunque la línea de ingreso continúe
        contabilizada en una cuenta 401.xx de ventas.
        """
        if not move:
            return self.env['account.account']
        for line in move.line_ids:
            account = line.account_id
            code = (account.code or '').strip() if account else ''
            name = self._systore_normalize_text(account.name if account else '')
            if code.startswith('106.') and 'transito' in name:
                return account
        return self.env['account.account']

    @api.model
    def _systore_sales_channel_from_account(self, account):
        """Canal comercial definido por la cuenta 401.xx de la línea facturada."""
        code = ((account.code or '') if account else '').strip()
        marketplace = {
            '401.01.01', '401.01.04', '401.01.04.01', '401.01.03', '401.01.05',
            '401.01.06', '401.01.07', '401.01.08', '401.01.14', '401.01.13',
            '401.01.21', '401.01.15', '401.01.20',
        }
        if code in marketplace:
            return 'Marketplace'
        if code in {'401.01.10', '402.01.10'}:
            return 'Mayoreo'
        if code in {'401.01.16', '401.01.12'}:
            return 'Empleado'
        return 'Sin clasificar'

    @api.depends('analytic_role')
    def _compute_is_transit_return(self):
        for rec in self:
            rec.is_transit_return = rec.analytic_role == 'transit_return'

    @api.depends('analytic_role', 'invoice_id.line_ids.account_id', 'invoice_id.line_ids.account_id.code', 'invoice_id.line_ids.account_id.name')
    def _compute_sale_state(self):
        for rec in self:
            transit_account = rec._systore_transit_counterpart(rec.invoice_id)
            rec.transit_account_id = transit_account
            rec.sale_state = 'return' if rec.analytic_role == 'transit_return' else 'sale'

    @api.depends('account_id.code')
    def _compute_sales_channel(self):
        for rec in self:
            rec.sales_channel = rec._systore_sales_channel_from_account(rec.account_id)

    @api.depends('allocated_sale_amount', 'matched_quantity', 'unit_cost_company')
    def _compute_profit(self):
        for rec in self:
            qty = abs(rec.matched_quantity or 0.0)
            rec.unit_sale_price = (rec.allocated_sale_amount / qty) if qty else 0.0
            rec.total_cost = (rec.unit_cost_company or 0.0) * qty
            # Utilidad solicitada a nivel unitario: precio unitario de venta - costo unitario.
            rec.gross_profit = (rec.unit_sale_price or 0.0) - (rec.unit_cost_company or 0.0)
            rec.total_profit = (rec.allocated_sale_amount or 0.0) - (rec.total_cost or 0.0)
            # Margen unitario; el widget percentage espera una razón (0.25 = 25 %).
            rec.gross_margin = (rec.gross_profit / rec.unit_sale_price) if rec.unit_sale_price else 0.0

    @api.depends('move_name', 'sku', 'lot_name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = ' / '.join(filter(None, [rec.move_name, rec.sku, rec.lot_name])) or _('Analítica')

    @api.model
    def _systore_order_base(self, origin):
        origin = (origin or '').strip()
        if not origin:
            return ''
        match = re.search(r'PR-\d{9}', origin, flags=re.IGNORECASE)
        if match:
            return match.group(0).upper()
        return origin[:12]

    @api.model
    def _systore_ml_qty(self, ml):
        if 'quantity_product_uom' in ml._fields:
            return ml.quantity_product_uom or 0.0
        qty = getattr(ml, 'quantity', 0.0) or 0.0
        if ml.product_uom_id and ml.product_id.uom_id and ml.product_uom_id != ml.product_id.uom_id:
            return ml.product_uom_id._compute_quantity(qty, ml.product_id.uom_id)
        return qty

    @api.model
    def _systore_physical_type(self, ml):
        if not ml:
            return 'none'
        src = ml.location_id.usage
        dst = ml.location_dest_id.usage
        if dst == 'customer' and src != 'customer':
            return 'sale'
        if src == 'customer' and dst != 'customer':
            return 'return'
        return 'other'

    @api.model
    def _systore_find_stock_lines(self, aml, order_base, physical_type='sale'):
        """Obtiene movimientos candidatos del pedido, sin asumir que toda la entrega pertenece a esta factura."""
        MoveLine = self.env['stock.move.line'].sudo()
        sale_lines = aml.sale_line_ids if 'sale_line_ids' in aml._fields else self.env['sale.order.line']
        result = self.env['stock.move.line']
        if sale_lines:
            moves = sale_lines.mapped('move_ids').filtered(lambda m: m.state == 'done' and m.product_id == aml.product_id)
            result = moves.mapped('move_line_ids').filtered(
                lambda ml: self._systore_physical_type(ml) == physical_type and self._systore_ml_qty(ml) > 0
            )
        if result:
            return result.sorted(lambda ml: (ml.date or fields.Datetime.now(), ml.id))

        if order_base:
            domain = [
                ('state', '=', 'done'),
                ('product_id', '=', aml.product_id.id),
                '|', ('picking_id.origin', 'ilike', order_base), ('move_id.origin', 'ilike', order_base),
            ]
            result = MoveLine.search(domain, order='date,id')
            result = result.filtered(lambda ml: self._systore_physical_type(ml) == physical_type and self._systore_ml_qty(ml) > 0)
        return result

    @api.model
    def _systore_prior_invoiced_qty(self, aml, order_base=''):
        """Cantidad de la misma operación ya consumida por facturas anteriores.

        Se prioriza el vínculo nativo `sale_line_ids`; si no existe, se usa Orden base + SKU
        como fallback, replicando la conciliación que se hacía en Excel.
        """
        AML = self.env['account.move.line'].sudo()
        move = aml.move_id
        domain = [
            ('id', '!=', aml.id),
            ('company_id', '=', aml.company_id.id),
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', '=', move.move_type),
            ('product_id', '=', aml.product_id.id),
        ]
        if 'display_type' in AML._fields:
            domain.append(('display_type', '=', 'product'))
        if 'sale_line_ids' in aml._fields and aml.sale_line_ids:
            domain.append(('sale_line_ids', 'in', aml.sale_line_ids.ids))
        elif order_base:
            domain.append(('move_id.invoice_origin', 'ilike', order_base))
        else:
            return 0.0

        current_date = move.invoice_date or move.date
        previous = AML.search(domain)
        previous = previous.filtered(lambda line:
            ((line.move_id.invoice_date or line.move_id.date) < current_date) or
            ((line.move_id.invoice_date or line.move_id.date) == current_date and
             (line.move_id.id, line.id) < (move.id, aml.id))
        )
        return sum(abs(line.quantity or 0.0) for line in previous)

    @api.model
    def _systore_allocate_invoice_qty(self, aml, order_base):
        """Asigna únicamente las piezas de esta factura a los lotes físicos, en FIFO.

        La factura es la autoridad de cantidad. Los movimientos solo determinan de qué lotes
        provienen esas piezas. Las cantidades facturadas previamente se saltan para no duplicar
        entregas históricas de una misma orden de venta.
        """
        target_qty = abs(aml.quantity or 0.0)
        if not target_qty:
            return [], 0.0

        physical_type = 'return' if aml.move_id.move_type == 'out_refund' else 'sale'
        stock_lines = self._systore_find_stock_lines(aml, order_base, physical_type=physical_type)
        if not stock_lines:
            return [], 0.0

        skip_qty = self._systore_prior_invoiced_qty(aml, order_base)
        remaining = target_qty
        allocations = []

        for ml in stock_lines:
            available = abs(self._systore_ml_qty(ml))
            if not available:
                continue
            if skip_qty >= available - 1e-9:
                skip_qty -= available
                continue
            if skip_qty > 0:
                available -= skip_qty
                skip_qty = 0.0
            take = min(available, remaining)
            if take > 1e-9:
                allocations.append((ml, take))
                remaining -= take
            if remaining <= 1e-9:
                break

        return allocations, target_qty - remaining

    @api.model
    def _systore_purchase_for_lot(self, product, lot, company):
        if not lot or not lot.name:
            return (False, False, False, 0.0, False, '')
        PO = self.env['purchase.order'].sudo()
        POL = self.env['purchase.order.line'].sudo()
        po = PO.search([('name', '=', lot.name), ('company_id', '=', company.id)], limit=1)
        if not po:
            return (False, False, False, 0.0, False, _('No se encontró OC con nombre = lote %s') % lot.name)

        lookup_product = product
        discount_factor = 1.0
        tmpl = product.product_tmpl_id
        if 'systore_is_open_box' in tmpl._fields and tmpl.systore_is_open_box:
            origin_sku = (tmpl.systore_open_box_origin_sku or '').strip() if 'systore_open_box_origin_sku' in tmpl._fields else ''
            if origin_sku:
                origin_product = self.env['product.product'].sudo().with_context(active_test=False).search([
                    ('default_code', '=', origin_sku),
                    ('company_id', 'in', [company.id, False]),
                ], limit=1)
                if origin_product:
                    lookup_product = origin_product
                    discount_factor = 0.85

        pol = POL.search([('order_id', '=', po.id), ('product_id', '=', lookup_product.id)], limit=1)
        if not pol:
            return (po, False, po.currency_id, 0.0, po.partner_id, _('No se encontró línea de OC para el SKU'))
        return (po, pol, pol.currency_id or po.currency_id, (pol.price_unit or 0.0) * discount_factor, po.partner_id, '')

    @api.model
    def _systore_field_display(self, record, field_name):
        """Devuelve un valor legible de un campo Studio sin asumir su tipo."""
        if not record or field_name not in record._fields:
            return ''
        value = record[field_name]
        field = record._fields[field_name]
        if not value:
            return ''
        if field.type == 'many2one':
            return value.display_name or ''
        if field.type in ('many2many', 'one2many'):
            return ', '.join(value.mapped('display_name'))
        if field.type == 'selection':
            selection = field._description_selection(record.env)
            return dict(selection).get(value, value)
        return str(value)

    @api.model
    def _systore_sale_context(self, aml, ml=None, order_base=''):
        """Obtiene línea/pedido de venta, priorizando la relación del movimiento físico."""
        sale_line = self.env['sale.order.line']
        if ml and ml.move_id and 'sale_line_id' in ml.move_id._fields and ml.move_id.sale_line_id:
            sale_line = ml.move_id.sale_line_id
        elif 'sale_line_ids' in aml._fields and aml.sale_line_ids:
            sale_line = aml.sale_line_ids[:1]

        sale_order = sale_line.order_id if sale_line else self.env['sale.order']
        if not sale_order and order_base:
            # Fallback para instalaciones donde la factura perdió el enlace nativo a sale.order.line.
            sale_order = self.env['sale.order'].sudo().search([
                ('company_id', '=', aml.company_id.id),
                '|', ('name', 'ilike', order_base), ('client_order_ref', 'ilike', order_base),
            ], limit=1)
        return sale_line, sale_order

    @api.model
    def rebuild_range(self, date_from, date_to, company=None):
        company = company or self.env.company
        self.search([
            ('company_id', '=', company.id),
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
        ]).unlink()

        AML = self.env['account.move.line'].sudo()
        domain = [
            ('company_id', '=', company.id),
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
            # RINV se filtra después de la búsqueda: únicamente 402.01.10 (Mayoreo)
            # participa en esta fase como devolución en tránsito y efectiva simultáneamente.
            ('move_id.invoice_date', '>=', date_from),
            ('move_id.invoice_date', '<=', date_to),
            ('product_id', '!=', False),
            ('account_id.account_type', 'in', ['income', 'income_other']),
        ]
        if 'display_type' in AML._fields:
            domain.append(('display_type', '=', 'product'))
        lines = AML.search(domain, order='move_id, id')
        created = 0

        for aml in lines:
            move_name_upper = ((aml.move_id.name or '') + ' ' + (aml.move_id.ref or '')).upper()
            is_rinv = 'RINV' in move_name_upper
            is_wholesale_rinv = is_rinv and (aml.account_id.code or '').strip() == '402.01.10'
            # Marketplace/otros RINV continúan reservados para el futuro reporte de devolución efectiva.
            if is_rinv and not is_wholesale_rinv:
                continue
            move = aml.move_id
            order_base = self._systore_order_base(move.invoice_origin)
            sku = aml.product_id.default_code or ''
            invoice_match_code = '%s%s' % (order_base, sku)
            allocations, allocated_invoice_qty = self._systore_allocate_invoice_qty(aml, order_base)
            inv_qty = abs(aml.quantity or 0.0)
            accounting_amount = (aml.credit or 0.0) - (aml.debit or 0.0)

            if not allocations:
                fallback_sale_line, fallback_sale_order = self._systore_sale_context(aml, order_base=order_base)
                self.create({
                    'company_id': company.id,
                    'invoice_date': move.invoice_date or move.date,
                    'invoice_id': move.id,
                    'invoice_line_id': aml.id,
                    'move_name': move.name,
                    'invoice_origin': move.invoice_origin,
                    'sale_origin': move.invoice_origin or (fallback_sale_order.name if fallback_sale_order else ''),
                    'order_base': order_base,
                    'ref': move.ref,
                    'account_id': aml.account_id.id,
                    'partner_id': move.partner_id.id,
                    'customer_contact_id': ((fallback_sale_order.partner_shipping_id.id if fallback_sale_order and fallback_sale_order.partner_shipping_id else False) or (move.partner_shipping_id.id if getattr(move, 'partner_shipping_id', False) else move.partner_id.id)),
                    'sale_order_id': fallback_sale_order.id if fallback_sale_order else False,
                    'salesperson_id': (fallback_sale_order.user_id.id if fallback_sale_order and fallback_sale_order.user_id else (move.invoice_user_id.id if getattr(move, 'invoice_user_id', False) else False)),
                    'analytic_role': 'transit_return' if is_wholesale_rinv else 'sale',
                    'sale_order_line_id': fallback_sale_line.id if fallback_sale_line else False,
                    'marketplace_order_number': self._systore_field_display(fallback_sale_order, 'x_studio_nmero_de_orden_mkp'),
                    'product_id': aml.product_id.id,
                    'sku': sku,
                    'product_name': aml.product_id.name,
                    'invoice_quantity': aml.quantity,
                    'matched_quantity': 0.0,
                    'invoice_credit': aml.credit,
                    'invoice_debit': aml.debit,
                    'accounting_amount': accounting_amount,
                    'allocated_sale_amount': accounting_amount,
                    'invoice_match_code': invoice_match_code,
                    'physical_move_type': 'none',
                    'reconciliation_state': 'no_stock',
                    'note': _('No se encontró movimiento físico por relación nativa ni por Orden base + SKU.'),
                })
                created += 1
                continue

            qty_basis = inv_qty or allocated_invoice_qty or 1.0
            qty_is_complete = abs(allocated_invoice_qty - inv_qty) <= 0.0001
            for ml, matched_qty in allocations:
                physical_type = self._systore_physical_type(ml)
                sale_line, sale_order = self._systore_sale_context(aml, ml=ml, order_base=order_base)
                sale_origin = (ml.picking_id.origin if ml.picking_id else False) or (ml.move_id.origin if ml.move_id else False) or move.invoice_origin or (sale_order.name if sale_order else '')
                signed_qty = -matched_qty if aml.move_id.move_type == 'out_refund' else matched_qty
                lot = ml.lot_id
                po, pol, po_currency, po_unit_cost, vendor, cost_note = self._systore_purchase_for_lot(aml.product_id, lot, company)

                company_unit_cost = 0.0
                if po_unit_cost and po_currency:
                    conversion_date = (po.date_order.date() if po and po.date_order else (move.invoice_date or fields.Date.today()))
                    company_unit_cost = po_currency._convert(po_unit_cost, company.currency_id, company, conversion_date)
                allocated_cost = company_unit_cost * signed_qty
                allocated_sale = accounting_amount * (matched_qty / qty_basis) if qty_basis else 0.0

                state = 'ok'
                note = cost_note
                if not lot:
                    state = 'no_stock'
                    note = _('Movimiento sin lote.')
                elif not po:
                    state = 'no_purchase'
                elif not pol or not po_unit_cost:
                    state = 'no_cost'
                elif not qty_is_complete:
                    state = 'qty_diff'
                    note = (note + ' ' if note else '') + _('No fue posible conciliar todas las piezas facturadas con movimientos físicos disponibles.')

                self.create({
                    'company_id': company.id,
                    'invoice_date': move.invoice_date or move.date,
                    'invoice_id': move.id,
                    'invoice_line_id': aml.id,
                    'move_name': move.name,
                    'invoice_origin': move.invoice_origin,
                    'sale_origin': sale_origin,
                    'order_base': order_base,
                    'ref': move.ref,
                    'account_id': aml.account_id.id,
                    'partner_id': move.partner_id.id,
                    'customer_contact_id': ((sale_order.partner_shipping_id.id if sale_order and sale_order.partner_shipping_id else False) or (move.partner_shipping_id.id if getattr(move, 'partner_shipping_id', False) else move.partner_id.id)),
                    'product_id': aml.product_id.id,
                    'sku': sku,
                    'product_name': aml.product_id.name,
                    'invoice_quantity': aml.quantity,
                    'matched_quantity': signed_qty,
                    'invoice_credit': aml.credit,
                    'invoice_debit': aml.debit,
                    'accounting_amount': accounting_amount,
                    'allocated_sale_amount': allocated_sale,
                    'sale_order_id': sale_order.id if sale_order else False,
                    'salesperson_id': (sale_order.user_id.id if sale_order and sale_order.user_id else (move.invoice_user_id.id if getattr(move, 'invoice_user_id', False) else False)),
                    'analytic_role': 'transit_return' if is_wholesale_rinv else 'sale',
                    'sale_order_line_id': sale_line.id if sale_line else False,
                    'marketplace_order_number': self._systore_field_display(sale_order, 'x_studio_nmero_de_orden_mkp'),
                    'stock_move_line_id': ml.id,
                    'picking_id': ml.picking_id.id if ml.picking_id else False,
                    'movement_date': ml.date,
                    'location_id': ml.location_id.id,
                    'location_dest_id': ml.location_dest_id.id,
                    'physical_move_type': physical_type,
                    'lot_id': lot.id if lot else False,
                    'lot_name': lot.name if lot else '',
                    'invoice_match_code': invoice_match_code,
                    'cost_match_code': '%s%s' % ((lot.name if lot else ''), sku),
                    'purchase_order_id': po.id if po else False,
                    'purchase_order_line_id': pol.id if pol else False,
                    'vendor_id': vendor.id if vendor else False,
                    'purchase_date': po.date_order if po else False,
                    'purchase_currency_id': po_currency.id if po_currency else company.currency_id.id,
                    'purchase_unit_cost': po_unit_cost,
                    'unit_cost_company': company_unit_cost,
                    'allocated_cost': allocated_cost,
                    'reconciliation_state': state,
                    'note': note,
                })
                created += 1

                # Una factura con contrapartida 106.xx Tránsito forma parte primero de la
                # venta bruta. Se agrega una segunda línea analítica negativa para descontarla
                # como devolución en tránsito y obtener la venta neta sin perder la venta original.
                transit_account = self._systore_transit_counterpart(move)
                if transit_account and not is_wholesale_rinv:
                    transit_vals = {
                        'company_id': company.id, 'invoice_date': move.invoice_date or move.date,
                        'invoice_id': move.id, 'invoice_line_id': aml.id, 'move_name': move.name,
                        'invoice_origin': move.invoice_origin, 'sale_origin': sale_origin, 'order_base': order_base,
                        'ref': move.ref, 'account_id': aml.account_id.id, 'partner_id': move.partner_id.id,
                        'customer_contact_id': ((sale_order.partner_shipping_id.id if sale_order and sale_order.partner_shipping_id else False) or (move.partner_shipping_id.id if getattr(move, 'partner_shipping_id', False) else move.partner_id.id)),
                        'product_id': aml.product_id.id, 'sku': sku, 'product_name': aml.product_id.name,
                        'invoice_quantity': -abs(aml.quantity or 0.0), 'matched_quantity': -abs(matched_qty),
                        'invoice_credit': 0.0, 'invoice_debit': abs(allocated_sale),
                        'accounting_amount': -abs(accounting_amount), 'allocated_sale_amount': -abs(allocated_sale),
                        'sale_order_id': sale_order.id if sale_order else False,
                        'salesperson_id': (sale_order.user_id.id if sale_order and sale_order.user_id else (move.invoice_user_id.id if getattr(move, 'invoice_user_id', False) else False)),
                        'analytic_role': 'transit_return',
                        'sale_order_line_id': sale_line.id if sale_line else False,
                        'marketplace_order_number': self._systore_field_display(sale_order, 'x_studio_nmero_de_orden_mkp'),
                        # NULL evita colisión de la restricción única y conserva lote/picking como trazabilidad.
                        'stock_move_line_id': False, 'picking_id': ml.picking_id.id if ml.picking_id else False,
                        'movement_date': ml.date, 'location_id': ml.location_id.id, 'location_dest_id': ml.location_dest_id.id,
                        'physical_move_type': physical_type, 'lot_id': lot.id if lot else False, 'lot_name': lot.name if lot else '',
                        'invoice_match_code': invoice_match_code, 'cost_match_code': '%s%s' % ((lot.name if lot else ''), sku),
                        'purchase_order_id': po.id if po else False, 'purchase_order_line_id': pol.id if pol else False,
                        'vendor_id': vendor.id if vendor else False, 'purchase_date': po.date_order if po else False,
                        'purchase_currency_id': po_currency.id if po_currency else company.currency_id.id,
                        'purchase_unit_cost': po_unit_cost, 'unit_cost_company': company_unit_cost,
                        'allocated_cost': -abs(company_unit_cost * matched_qty), 'reconciliation_state': state,
                        'note': _('Línea negativa generada por contrapartida de Tránsito: %s') % transit_account.display_name,
                    }
                    self.create(transit_vals)
                    created += 1
        return created

    @api.model
    def get_dashboard_data(self, filters=None):
        """Devuelve los datos agregados del primer tablero Systore.

        Venta/Devolución en tránsito se determina por la póliza de la factura. Si entre sus
        apuntes existe una contrapartida 106.xx cuyo nombre contiene Tránsito, la operación
        se considera devolución en tránsito. Las notas de crédito RINV (devolución efectiva)
        se excluyen salvo Mayoreo: RINV contabilizado en 402.01.10 se incorpora como
        devolución en tránsito y devolución efectiva a la vez.
        """
        filters = filters or {}
        today = fields.Date.context_today(self)
        date_from = filters.get('date_from') or today.replace(day=1)
        date_to = filters.get('date_to') or today
        if isinstance(date_from, str):
            date_from = fields.Date.from_string(date_from)
        if isinstance(date_to, str):
            date_to = fields.Date.from_string(date_to)

        base_domain = [
            ('company_id', '=', self.env.company.id),
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
        ]
        domain = list(base_domain)
        sale_states = filters.get('sale_state') or []
        if isinstance(sale_states, str):
            sale_states = [sale_states] if sale_states else []
        sale_states = [value for value in sale_states if value in ('sale', 'return')]
        if sale_states:
            domain.append(('sale_state', 'in', sale_states))

        sales_channels = filters.get('sales_channel') or []
        if isinstance(sales_channels, str):
            sales_channels = [sales_channels] if sales_channels else []
        if sales_channels:
            domain.append(('sales_channel', 'in', sales_channels))

        for field_name in ('account_id', 'partner_id', 'customer_contact_id', 'product_id', 'vendor_id', 'salesperson_id'):
            values = filters.get(field_name) or []
            if not isinstance(values, (list, tuple)):
                values = [values] if values else []
            values = [int(value) for value in values if value]
            if values:
                domain.append((field_name, 'in', values))

        records = self.search(domain, order='invoice_date, id')
        option_records = self.search(base_domain)

        metrics = {
            'gross_sales': 0.0, 'returns': 0.0, 'sale_cost': 0.0, 'return_cost': 0.0,
            'sale_pieces': 0.0, 'return_pieces': 0.0, 'issues': 0, 'total_lines': len(records),
        }
        trend = defaultdict(lambda: {'sales': 0.0, 'returns': 0.0, 'sale_cost': 0.0, 'return_cost': 0.0})
        channels = defaultdict(lambda: self._systore_dashboard_bucket())
        products = defaultdict(lambda: self._systore_dashboard_bucket())
        vendors = defaultdict(lambda: self._systore_dashboard_bucket())
        customers = defaultdict(lambda: self._systore_dashboard_bucket())
        contacts = defaultdict(lambda: self._systore_dashboard_bucket())
        reconciliation = defaultdict(int)

        for rec in records:
            amount = abs(rec.allocated_sale_amount or 0.0)
            cost = abs(rec.total_cost or 0.0)
            pieces = abs(rec.matched_quantity or 0.0)
            is_return = rec.sale_state == 'return'
            if is_return:
                metrics['returns'] += amount
                metrics['return_cost'] += cost
                metrics['return_pieces'] += pieces
            else:
                metrics['gross_sales'] += amount
                metrics['sale_cost'] += cost
                metrics['sale_pieces'] += pieces
            if rec.reconciliation_state != 'ok':
                metrics['issues'] += 1
            reconciliation[rec.reconciliation_state or 'unknown'] += 1

            day = fields.Date.to_string(rec.invoice_date) if rec.invoice_date else ''
            if day:
                if is_return:
                    trend[day]['returns'] += amount
                    trend[day]['return_cost'] += cost
                else:
                    trend[day]['sales'] += amount
                    trend[day]['sale_cost'] += cost

            channel_key = rec.sales_channel or 'Sin canal'
            product_key = rec.product_id.id or 0
            vendor_key = rec.vendor_id.id or 0
            customer_key = rec.partner_id.id or 0
            contact_key = rec.customer_contact_id.id or 0
            self._systore_add_dashboard_bucket(channels[channel_key], amount, cost, pieces, is_return)
            self._systore_add_dashboard_bucket(products[product_key], amount, cost, pieces, is_return)
            self._systore_add_dashboard_bucket(vendors[vendor_key], amount, cost, pieces, is_return)
            self._systore_add_dashboard_bucket(customers[customer_key], amount, cost, pieces, is_return)
            self._systore_add_dashboard_bucket(contacts[contact_key], amount, cost, pieces, is_return)

        net_sales = metrics['gross_sales'] - metrics['returns']
        net_cost = metrics['sale_cost'] - metrics['return_cost']
        profit = net_sales - net_cost
        net_pieces = metrics['sale_pieces'] - metrics['return_pieces']
        margin = profit / net_sales if net_sales else 0.0
        return_rate = metrics['returns'] / metrics['gross_sales'] if metrics['gross_sales'] else 0.0
        reconciliation_rate = ((metrics['total_lines'] - metrics['issues']) / metrics['total_lines']) if metrics['total_lines'] else 1.0

        trend_rows = []
        for day in sorted(trend):
            vals = trend[day]
            day_net_sales = vals['sales'] - vals['returns']
            day_net_cost = vals['sale_cost'] - vals['return_cost']
            trend_rows.append({
                'date': day,
                'label': fields.Date.from_string(day).strftime('%d/%m'),
                'gross_sales': vals['sales'],
                'returns': vals['returns'],
                'net_sales': day_net_sales,
                'net_cost': day_net_cost,
                'profit': day_net_sales - day_net_cost,
            })
        trend_max = max(
            [abs(row[x]) for row in trend_rows for x in ('net_sales', 'net_cost', 'profit')] or [0.0]
        )

        product_map = {r.id: '[%s] %s' % (r.default_code or '', r.name) if r.default_code else r.name for r in records.mapped('product_id')}
        vendor_map = {r.id: r.display_name for r in records.mapped('vendor_id')}
        customer_map = {r.id: r.display_name for r in records.mapped('partner_id')}
        contact_map = {r.id: r.display_name for r in records.mapped('customer_contact_id')}

        channel_rows = self._systore_dashboard_rows(channels, lambda key: key, lambda key: [('sales_channel', '=', key)] if key != 'Sin canal' else [('sales_channel', 'in', [False, ''])])
        product_rows = self._systore_dashboard_rows(products, lambda key: product_map.get(key, 'Sin producto'), lambda key: [('product_id', '=', key)] if key else [('product_id', '=', False)])
        vendor_rows = self._systore_dashboard_rows(vendors, lambda key: vendor_map.get(key, 'Sin proveedor'), lambda key: [('vendor_id', '=', key)] if key else [('vendor_id', '=', False)])
        customer_rows = self._systore_dashboard_rows(customers, lambda key: customer_map.get(key, 'Sin cliente'), lambda key: [('partner_id', '=', key)] if key else [('partner_id', '=', False)])
        contact_rows = self._systore_dashboard_rows(contacts, lambda key: contact_map.get(key, 'Sin contacto'), lambda key: [('customer_contact_id', '=', key)] if key else [('customer_contact_id', '=', False)])
        def pie_set(rows):
            return {
                'sales': self._systore_dashboard_pie_rows(rows, value_field='sales'),
                'returns': self._systore_dashboard_pie_rows(rows, value_field='returns'),
                'pieces': self._systore_dashboard_pie_rows(rows, value_field='gross_pieces'),
            }

        pie_sets = {
            'channels': pie_set(channel_rows),
            'customers': pie_set(customer_rows),
            'contacts': pie_set(contact_rows),
            'products': pie_set(product_rows),
            'vendors': pie_set(vendor_rows),
        }
        # Compatibilidad con versiones previas del cliente OWL.
        pie_channels = pie_sets['channels']['sales']
        pie_products = pie_sets['products']['sales']
        pie_vendors = pie_sets['vendors']['pieces']
        pie_customers = pie_sets['customers']['sales']
        pie_contacts = pie_sets['contacts']['sales']
        return_channel_rows = [row for row in channel_rows if row['returns'] > 0]
        return_channel_rows.sort(key=lambda row: row['returns'], reverse=True)

        state_labels = dict(self._fields['reconciliation_state']._description_selection(self.env))
        reconciliation_rows = []
        for key, count in sorted(reconciliation.items(), key=lambda item: (item[0] != 'ok', -item[1])):
            reconciliation_rows.append({
                'key': key,
                'label': state_labels.get(key, key),
                'count': count,
                'rate': count / metrics['total_lines'] if metrics['total_lines'] else 0.0,
                'domain': [('reconciliation_state', '=', key)],
            })

        return {
            'currency': self.env.company.currency_id.name or 'MXN',
            'applied_filters': {
                'date_from': fields.Date.to_string(date_from),
                'date_to': fields.Date.to_string(date_to),
            },
            'kpis': {
                **metrics,
                'net_sales': net_sales,
                'net_cost': net_cost,
                'profit': profit,
                'margin': margin,
                'net_pieces': net_pieces,
                'return_rate': return_rate,
                'reconciliation_rate': reconciliation_rate,
            },
            'trend': trend_rows,
            'trend_max': trend_max,
            'channels': channel_rows[:10],
            'products': product_rows[:10],
            'vendors': vendor_rows[:10],
            'pie_channels': pie_channels,
            'pie_products': pie_products,
            'pie_vendors': pie_vendors,
            'pie_customers': pie_customers,
            'pie_contacts': pie_contacts,
            'pie_sets': pie_sets,
            'return_channels': return_channel_rows[:10],
            'reconciliation': reconciliation_rows,
            'filters': self._systore_dashboard_filter_options(option_records),
        }

    @api.model
    def _systore_dashboard_bucket(self):
        return {'sales': 0.0, 'returns': 0.0, 'sale_cost': 0.0, 'return_cost': 0.0, 'sale_pieces': 0.0, 'return_pieces': 0.0}

    @api.model
    def _systore_add_dashboard_bucket(self, bucket, amount, cost, pieces, is_return):
        if is_return:
            bucket['returns'] += amount
            bucket['return_cost'] += cost
            bucket['return_pieces'] += pieces
        else:
            bucket['sales'] += amount
            bucket['sale_cost'] += cost
            bucket['sale_pieces'] += pieces

    @api.model
    def _systore_dashboard_rows(self, buckets, label_getter, domain_getter):
        rows = []
        for key, bucket in buckets.items():
            net_sales = bucket['sales'] - bucket['returns']
            net_cost = bucket['sale_cost'] - bucket['return_cost']
            profit = net_sales - net_cost
            rows.append({
                'key': str(key),
                'label': label_getter(key) or 'Sin dato',
                'sales': bucket['sales'],
                'returns': bucket['returns'],
                'net_sales': net_sales,
                'net_cost': net_cost,
                'profit': profit,
                'margin': profit / net_sales if net_sales else 0.0,
                'pieces': bucket['sale_pieces'] - bucket['return_pieces'],
                'sale_pieces': bucket['sale_pieces'],
                'return_pieces': bucket['return_pieces'],
                'gross_pieces': bucket['sale_pieces'] + bucket['return_pieces'],
                'domain': domain_getter(key),
            })
        rows.sort(key=lambda row: row['net_sales'], reverse=True)
        return rows

    @api.model
    def _systore_dashboard_pie_rows(self, rows, limit=7, value_field='sales'):
        """Prepara una distribución positiva para pastel a partir de una medida agregada."""
        positive = [dict(row) for row in rows if (row.get(value_field) or 0.0) > 0]
        positive.sort(key=lambda row: row.get(value_field, 0.0), reverse=True)
        total = sum(row.get(value_field, 0.0) for row in positive)
        if not total:
            return []
        visible = positive[:limit]
        remainder = positive[limit:]
        result = []
        for row in visible:
            result.append({
                'key': row.get('key'),
                'label': row.get('label') or 'Sin dato',
                'value': row.get(value_field, 0.0),
                'share': row.get(value_field, 0.0) / total,
                'pieces': (row.get('return_pieces', 0.0) if value_field == 'returns' else (row.get('sale_pieces', 0.0) if value_field == 'sales' else row.get('gross_pieces', 0.0))),
                'domain': row.get('domain', []),
            })
        if remainder:
            other_value = sum(row.get(value_field, 0.0) for row in remainder)
            other_pieces = sum((row.get('return_pieces', 0.0) if value_field == 'returns' else (row.get('sale_pieces', 0.0) if value_field == 'sales' else row.get('gross_pieces', 0.0))) for row in remainder)
            result.append({
                'key': '__other__',
                'label': 'Otros',
                'value': other_value,
                'share': other_value / total,
                'pieces': other_pieces,
                'domain': [],
            })
        return result

    @api.model
    def _systore_dashboard_filter_options(self, records):
        def m2o_options(recs):
            return [{'id': rec.id, 'name': rec.display_name} for rec in recs.sorted(lambda r: (r.display_name or '').lower())]

        channels = sorted(set(filter(None, records.mapped('sales_channel'))))
        products = records.mapped('product_id')
        product_options = []
        for product in products.sorted(lambda r: ((r.default_code or ''), (r.name or ''))):
            label = '[%s] %s' % (product.default_code, product.name) if product.default_code else product.name
            product_options.append({'id': product.id, 'name': label})
        return {
            'sales_channels': channels,
            'accounts': m2o_options(records.mapped('account_id')),
            'partners': m2o_options(records.mapped('partner_id')),
            'contacts': m2o_options(records.mapped('customer_contact_id')),
            'products': product_options,
            'vendors': m2o_options(records.mapped('vendor_id')),
            'salespersons': m2o_options(records.mapped('salesperson_id')),
        }

