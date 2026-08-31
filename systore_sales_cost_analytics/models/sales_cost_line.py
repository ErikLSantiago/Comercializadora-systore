# -*- coding: utf-8 -*-
import re

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
    invoice_origin = fields.Char(string='Origen factura', index=True, readonly=True)
    order_base = fields.Char(string='Orden base', index=True, readonly=True)
    ref = fields.Char(string='Referencia', readonly=True)

    account_id = fields.Many2one('account.account', string='Cuenta contable', index=True, readonly=True)
    account_analytics_type = fields.Selection(related='account_id.systore_analytics_type', string='Tipo cuenta', store=True, readonly=True)
    is_transit_return = fields.Boolean(string='Devolución bruta (cuenta tránsito)', compute='_compute_is_transit_return', store=True)

    partner_id = fields.Many2one('res.partner', string='Cliente', index=True, readonly=True)
    product_id = fields.Many2one('product.product', string='Producto', index=True, readonly=True)
    sku = fields.Char(string='SKU', index=True, readonly=True)
    product_name = fields.Char(string='Descripción producto', readonly=True)

    invoice_quantity = fields.Float(string='Cantidad facturada', readonly=True)
    matched_quantity = fields.Float(string='Cantidad conciliada', readonly=True)
    invoice_credit = fields.Monetary(string='Crédito', currency_field='company_currency_id', readonly=True)
    invoice_debit = fields.Monetary(string='Débito', currency_field='company_currency_id', readonly=True)
    accounting_amount = fields.Monetary(string='Venta contable', currency_field='company_currency_id', readonly=True,
        help='Crédito menos débito de la línea contable.')
    allocated_sale_amount = fields.Monetary(string='Venta asignada', currency_field='company_currency_id', readonly=True,
        help='Venta contable distribuida proporcionalmente entre los lotes conciliados.')

    sale_order_id = fields.Many2one('sale.order', string='Pedido de venta', index=True, readonly=True)
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
    allocated_cost = fields.Monetary(string='Costo asignado', currency_field='company_currency_id', readonly=True)
    gross_profit = fields.Monetary(string='Utilidad', currency_field='company_currency_id', compute='_compute_profit', store=True)
    gross_margin = fields.Float(string='Margen %', compute='_compute_profit', store=True, group_operator='avg')

    reconciliation_state = fields.Selection([
        ('ok', 'Conciliado'),
        ('no_stock', 'Sin movimiento/lote'),
        ('no_purchase', 'Sin compra'),
        ('no_cost', 'Sin costo'),
        ('qty_diff', 'Diferencia de cantidad'),
    ], string='Estado conciliación', index=True, readonly=True)
    note = fields.Char(string='Observación', readonly=True)

    display_name = fields.Char(compute='_compute_display_name')

    _sql_constraints = [
        ('invoice_stock_unique', 'unique(invoice_line_id, stock_move_line_id, lot_id)',
         'La combinación de línea de factura y movimiento/lote ya existe.'),
    ]

    @api.depends('account_analytics_type')
    def _compute_is_transit_return(self):
        for rec in self:
            rec.is_transit_return = rec.account_analytics_type == 'transit_return'

    @api.depends('allocated_sale_amount', 'allocated_cost')
    def _compute_profit(self):
        for rec in self:
            rec.gross_profit = (rec.allocated_sale_amount or 0.0) - (rec.allocated_cost or 0.0)
            rec.gross_margin = (rec.gross_profit / rec.allocated_sale_amount * 100.0) if rec.allocated_sale_amount else 0.0

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
    def _systore_find_stock_lines(self, aml, order_base):
        MoveLine = self.env['stock.move.line'].sudo()
        sale_lines = aml.sale_line_ids if 'sale_line_ids' in aml._fields else self.env['sale.order.line']
        result = self.env['stock.move.line']
        if sale_lines:
            moves = sale_lines.mapped('move_ids').filtered(lambda m: m.state == 'done' and m.product_id == aml.product_id)
            result = moves.mapped('move_line_ids').filtered(
                lambda ml: self._systore_physical_type(ml) in ('sale', 'return') and self._systore_ml_qty(ml) > 0
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
            result = result.filtered(lambda ml: self._systore_physical_type(ml) in ('sale', 'return'))
        return result

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
            move = aml.move_id
            order_base = self._systore_order_base(move.invoice_origin)
            sku = aml.product_id.default_code or ''
            invoice_match_code = '%s%s' % (order_base, sku)
            stock_lines = self._systore_find_stock_lines(aml, order_base)
            inv_qty = abs(aml.quantity or 0.0)
            accounting_amount = (aml.credit or 0.0) - (aml.debit or 0.0)

            if not stock_lines:
                self.create({
                    'company_id': company.id,
                    'invoice_date': move.invoice_date or move.date,
                    'invoice_id': move.id,
                    'invoice_line_id': aml.id,
                    'move_name': move.name,
                    'invoice_origin': move.invoice_origin,
                    'order_base': order_base,
                    'ref': move.ref,
                    'account_id': aml.account_id.id,
                    'partner_id': move.partner_id.id,
                    'product_id': aml.product_id.id,
                    'sku': sku,
                    'product_name': aml.product_id.display_name,
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

            total_stock_qty = sum(self._systore_ml_qty(x) for x in stock_lines if self._systore_physical_type(x) == 'sale')
            qty_basis = inv_qty or total_stock_qty or 1.0
            sale_lines_rel = aml.sale_line_ids if 'sale_line_ids' in aml._fields else self.env['sale.order.line']
            sale_order = sale_lines_rel[:1].order_id if sale_lines_rel else False

            for ml in stock_lines:
                physical_type = self._systore_physical_type(ml)
                ml_qty = self._systore_ml_qty(ml)
                signed_qty = -ml_qty if physical_type == 'return' else ml_qty
                lot = ml.lot_id
                po, pol, po_currency, po_unit_cost, vendor, cost_note = self._systore_purchase_for_lot(aml.product_id, lot, company)

                company_unit_cost = 0.0
                if po_unit_cost and po_currency:
                    conversion_date = (po.date_order.date() if po and po.date_order else (move.invoice_date or fields.Date.today()))
                    company_unit_cost = po_currency._convert(po_unit_cost, company.currency_id, company, conversion_date)
                allocated_cost = company_unit_cost * signed_qty
                allocated_sale = accounting_amount * (signed_qty / qty_basis) if qty_basis else 0.0

                state = 'ok'
                note = cost_note
                if not lot:
                    state = 'no_stock'
                    note = _('Movimiento sin lote.')
                elif not po:
                    state = 'no_purchase'
                elif not pol or not po_unit_cost:
                    state = 'no_cost'
                elif total_stock_qty and inv_qty and abs(total_stock_qty - inv_qty) > 0.0001:
                    state = 'qty_diff'
                    note = (note + ' ' if note else '') + _('Cantidad facturada y salida física no coinciden.')

                self.create({
                    'company_id': company.id,
                    'invoice_date': move.invoice_date or move.date,
                    'invoice_id': move.id,
                    'invoice_line_id': aml.id,
                    'move_name': move.name,
                    'invoice_origin': move.invoice_origin,
                    'order_base': order_base,
                    'ref': move.ref,
                    'account_id': aml.account_id.id,
                    'partner_id': move.partner_id.id,
                    'product_id': aml.product_id.id,
                    'sku': sku,
                    'product_name': aml.product_id.display_name,
                    'invoice_quantity': aml.quantity,
                    'matched_quantity': signed_qty,
                    'invoice_credit': aml.credit,
                    'invoice_debit': aml.debit,
                    'accounting_amount': accounting_amount,
                    'allocated_sale_amount': allocated_sale,
                    'sale_order_id': sale_order.id if sale_order else False,
                    'sale_order_line_id': sale_lines_rel[:1].id if sale_lines_rel else False,
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
        return created
