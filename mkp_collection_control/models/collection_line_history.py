from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare
from dateutil.relativedelta import relativedelta

from .ledger import collection_line_totals, validate_return_quantity


MONETARY_REVISION_FIELDS = (
    'coupon_amount',
    'killer_amount',
    'killer_commission',
    'commission',
    'taxes',
    'shipping',
    'other_commission',
)

NON_MONETARY_REVISION_FIELDS = (
    'payment_status',
    'payment_reference',
    'calculation_type',
    'return_status',
    'return_request_date',
    'return_reference',
)
QUANTITY_REVISION_FIELDS = ('return_quantity',)
REVISION_FIELDS = (
    MONETARY_REVISION_FIELDS
    + NON_MONETARY_REVISION_FIELDS
    + QUANTITY_REVISION_FIELDS
)

BASE_FIELDS = (
    'sequence',
    'product_id',
    'sku',
    'product_name',
    'quantity',
    'uom_name',
    'price_unit',
    'amount',
)


class MkpCollectionLineHistory(models.Model):
    _name = 'mkp.collection.line.history'
    _description = 'Historial de cobranza por línea de venta'
    _order = 'sale_order_id desc, sequence, sale_line_id, revision_no desc, id desc'
    _rec_name = 'name'

    name = fields.Char('Movimiento', required=True, readonly=True, index=True)
    revision_key = fields.Char('Clave de línea', required=True, readonly=True, index=True)
    revision_no = fields.Integer('Revisión', required=True, readonly=True, default=1)
    previous_id = fields.Many2one(
        'mkp.collection.line.history', string='Versión anterior', readonly=True,
        ondelete='restrict'
    )
    is_active_revision = fields.Boolean(
        'Activo', required=True, readonly=True, default=True, index=True
    )
    history_status = fields.Selection([
        ('active', 'Activo'),
        ('historical', 'Histórico'),
    ], string='Estatus', compute='_compute_history_status', store=True)
    change_origin = fields.Selection([
        ('initial', 'Carga inicial'),
        ('manual', 'Modificación de cobranza'),
        ('sale_sync', 'Cambio en Ventas'),
        ('import', 'Importación'),
    ], string='Origen', required=True, readonly=True, default='manual')
    comment = fields.Text('Comentario')

    order_id = fields.Many2one(
        'mkp.collection.order', string='Expediente', required=True, readonly=True,
        index=True, ondelete='restrict'
    )
    sale_order_id = fields.Many2one(
        related='order_id.sale_order_id', string='Orden de venta', store=True,
        readonly=True, index=True
    )
    sale_line_id = fields.Many2one(
        'sale.order.line', string='Línea de venta', readonly=True, index=True,
        ondelete='set null'
    )
    company_id = fields.Many2one(related='order_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(related='order_id.currency_id', store=True, readonly=True)
    marketplace = fields.Char(related='order_id.marketplace', store=True, readonly=True)
    marketplace_reference = fields.Char(
        related='order_id.marketplace_reference', store=True, readonly=True
    )
    partner_invoice_id = fields.Many2one(
        related='sale_order_id.partner_invoice_id', string='Cliente', store=True,
        readonly=True, index=True
    )
    invoice_date = fields.Date(
        'Fecha de factura', compute='_compute_invoice_date', compute_sudo=True,
        readonly=True
    )
    import_sale_order_id = fields.Many2one(
        'sale.order', string='Orden de venta', ondelete='restrict',
        help='Campo de identificación utilizado únicamente durante la importación.'
    )

    sequence = fields.Integer('Secuencia')
    product_id = fields.Many2one('product.product', string='Producto',
                                 ondelete='set null')
    sku = fields.Char('SKU', index=True)
    product_name = fields.Char('Producto', required=True, readonly=True, index=True)
    quantity = fields.Float('Cantidad', digits='Product Unit of Measure', readonly=True)
    uom_name = fields.Char('Unidad', readonly=True)
    price_unit = fields.Monetary('Precio unitario', currency_field='currency_id', readonly=True)
    amount = fields.Monetary('Importe', currency_field='currency_id', readonly=True)

    coupon_amount = fields.Monetary('Cupón', currency_field='currency_id')
    coupon_commission = fields.Monetary(
        'Comisión cupón', currency_field='currency_id', readonly=True
    )
    killer_amount = fields.Monetary('Killer', currency_field='currency_id')
    killer_commission = fields.Monetary(
        'Comisión killer', currency_field='currency_id'
    )
    commission = fields.Monetary('Comisiones', currency_field='currency_id')
    taxes = fields.Monetary('Impuestos', currency_field='currency_id')
    shipping = fields.Monetary('Envío', currency_field='currency_id')
    other_commission = fields.Monetary(
        'Otras comisiones', currency_field='currency_id'
    )
    calculation_type = fields.Selection([
        ('precalculation', 'Precalculo'),
        ('marketplace', 'Marketplace'),
    ], string='Tipo de cálculo', required=True,
       default='precalculation', index=True)
    payment_status = fields.Selection([
        ('held', 'Retenido'),
        ('pending', 'Pendiente'),
        ('paid', 'Pagado'),
        ('cancelled', 'Cancelado'),
        ('refund', 'Reembolso'),
    ], string='Estado de pago', required=True,
       default='pending', index=True)
    payment_reference = fields.Char('Referencia de pago', index=True)
    return_status = fields.Selection([
        ('created', 'Devolución creada'),
        ('new', 'Nuevo'),
        ('open_box', 'Open box'),
        ('claim_payment', 'Pago por reclamo'),
        ('subtraction', 'Sustracción'),
        ('refund', 'Reembolso'),
        ('sale', 'Venta'),
    ], string='Estado de devolución', required=True,
       default='sale', index=True)
    return_request_date = fields.Date('Fecha de solicitud', index=True)
    return_reference = fields.Char('Referencia', index=True)
    return_quantity = fields.Float(
        'Cantidad a devolver', digits='Product Unit of Measure',
        default=0
    )
    subtotal = fields.Monetary(
        'Sub total', currency_field='currency_id', compute='_compute_totals', store=True
    )
    adjusted_total = fields.Monetary(
        'Total ajustado', currency_field='currency_id', compute='_compute_totals', store=True
    )
    amount_to_collect = fields.Monetary(
        'Por cobrar', currency_field='currency_id', compute='_compute_totals', store=True
    )

    changed_by_id = fields.Many2one(
        related='create_uid', string='Modificado por', readonly=True, store=True
    )
    changed_at = fields.Datetime(
        related='create_date', string='Fecha de modificación', readonly=True, store=True
    )

    _sql_constraints = [
        (
            'unique_sale_line_revision',
            'unique(revision_key, revision_no)',
            'La revisión de esta línea de cobranza ya existe.',
        ),
    ]

    @api.depends('is_active_revision')
    def _compute_history_status(self):
        for record in self:
            record.history_status = 'active' if record.is_active_revision else 'historical'

    @api.depends(
        'sale_order_id.invoice_ids.invoice_date',
        'sale_order_id.invoice_ids.state',
        'sale_order_id.invoice_ids.move_type',
    )
    def _compute_invoice_date(self):
        for record in self:
            invoices = record.sale_order_id.invoice_ids.filtered(
                lambda invoice: invoice.move_type == 'out_invoice'
                and invoice.state != 'cancel'
                and invoice.invoice_date
            )
            record.invoice_date = max(invoices.mapped('invoice_date'), default=False)

    @api.model
    def get_dashboard_data(self, filters=None):
        filters = filters or {}
        base_domain = [
            ('is_active_revision', '=', True),
            ('company_id', '=', self.env.company.id),
        ]
        domain = list(base_domain)
        date_from = fields.Date.to_date(filters.get('date_from')) \
            if filters.get('date_from') else False
        date_to = fields.Date.to_date(filters.get('date_to')) \
            if filters.get('date_to') else False
        month_start = False
        if filters.get('month'):
            try:
                month_start = fields.Date.to_date('%s-01' % filters['month'])
            except (TypeError, ValueError):
                month_start = False
        if filters.get('state'):
            domain.append(('payment_status', '=', filters['state']))
        if filters.get('partner_id'):
            try:
                partner_id = int(filters['partner_id'])
            except (TypeError, ValueError):
                partner_id = 0
            if partner_id:
                domain.append(('partner_invoice_id', '=', partner_id))
        order_filters = []
        if filters.get('has_killer'):
            order_filters.append(('killer_amount', '>', 0))
        if filters.get('has_coupon'):
            order_filters.append(('coupon_amount', '>', 0))
        if filters.get('has_return'):
            order_filters.append(('return_status', '!=', 'sale'))
        for condition in order_filters:
            matching_order_ids = self.search(
                base_domain + [condition]
            ).mapped('sale_order_id').ids
            domain.append(('sale_order_id', 'in', matching_order_ids))

        dashboard_fields = [
            'sale_order_id', 'invoice_date', 'partner_invoice_id',
            'payment_status', 'return_status', 'amount', 'coupon_amount',
            'killer_amount', 'killer_commission', 'commission', 'taxes',
            'shipping', 'other_commission', 'amount_to_collect',
            'return_quantity',
        ]
        records = self.search(domain)
        values = records.read(dashboard_fields)
        if date_from or date_to or month_start:
            month_end = month_start + relativedelta(months=1) if month_start else False
            filtered_values = []
            for row in values:
                row_date = fields.Date.to_date(row.get('invoice_date')) \
                    if row.get('invoice_date') else False
                if not row_date:
                    continue
                if date_from and row_date < date_from:
                    continue
                if date_to and row_date > date_to:
                    continue
                if month_start and not (month_start <= row_date < month_end):
                    continue
                filtered_values.append(row)
            values = filtered_values

        def total(field_name):
            return sum((row.get(field_name) or 0.0) for row in values)

        totals = {
            'amount': total('amount'),
            'coupon': total('coupon_amount'),
            'killer': total('killer_amount'),
            'killer_commission': total('killer_commission'),
            'commission': total('commission'),
            'taxes': total('taxes'),
            'shipping': total('shipping'),
            'other_commission': total('other_commission'),
            'amount_to_collect': total('amount_to_collect'),
            'return_quantity': total('return_quantity'),
        }
        totals['adjusted_base'] = totals['amount'] + totals['killer']
        totals['total_commissions'] = (
            totals['commission']
            + totals['killer_commission']
            + totals['other_commission']
        )
        totals['total_deductions'] = (
            totals['coupon']
            + totals['killer_commission']
            + totals['commission']
            + totals['taxes']
            + totals['shipping']
            + totals['other_commission']
        )

        composition = [
            {'key': 'collect', 'label': _('Por cobrar'),
             'value': max(totals['amount_to_collect'], 0), 'color': '#16a765'},
            {'key': 'commission', 'label': _('Comisiones'),
             'value': totals['commission'], 'color': '#7c5cfc'},
            {'key': 'shipping', 'label': _('Envío'),
             'value': totals['shipping'], 'color': '#3b82f6'},
            {'key': 'taxes', 'label': _('Retenciones / impuestos'),
             'value': totals['taxes'], 'color': '#f59e0b'},
            {'key': 'killer_commission', 'label': _('Comisión killer'),
             'value': totals['killer_commission'], 'color': '#ef4444'},
            {'key': 'other', 'label': _('Otras comisiones'),
             'value': totals['other_commission'], 'color': '#64748b'},
            {'key': 'coupon', 'label': _('Cupón'),
             'value': totals['coupon'], 'color': '#ec4899'},
        ]
        composition_total = sum(item['value'] for item in composition if item['value'] > 0)
        for item in composition:
            item['percentage'] = (
                item['value'] * 100 / composition_total
                if composition_total and item['value'] > 0 else 0
            )

        payment_labels = dict(
            self._fields['payment_status']._description_selection(self.env)
        )
        payment_totals = {}
        for row in values:
            status = row.get('payment_status') or 'pending'
            payment_totals[status] = payment_totals.get(status, 0) + (
                row.get('amount_to_collect') or 0.0
            )
        payment_colors = {
            'held': '#f59e0b', 'pending': '#64748b', 'paid': '#16a765',
            'cancelled': '#ef4444', 'refund': '#8b5cf6',
        }
        payment_breakdown = [
            {
                'key': key,
                'label': payment_labels.get(key, key),
                'value': payment_totals.get(key, 0),
                'color': payment_colors.get(key, '#64748b'),
            }
            for key in payment_labels
        ]

        base_values = self.search(base_domain).read([
            'invoice_date', 'partner_invoice_id'
        ])
        month_keys = sorted({
            fields.Date.to_date(row['invoice_date']).strftime('%Y-%m')
            for row in base_values if row.get('invoice_date')
        }, reverse=True)
        clients = {}
        for row in base_values:
            partner = row.get('partner_invoice_id')
            if partner:
                clients[partner[0]] = partner[1]

        return {
            'totals': totals,
            'counts': {
                'lines': len(values),
                'orders': len({row['sale_order_id'][0] for row in values
                               if row.get('sale_order_id')}),
                'returns': sum(1 for row in values
                               if row.get('return_status') != 'sale'),
            },
            'composition': composition,
            'composition_total': composition_total,
            'payment_breakdown': payment_breakdown,
            'options': {
                'months': month_keys,
                'clients': [
                    {'id': partner_id, 'name': clients[partner_id]}
                    for partner_id in sorted(clients, key=lambda item: clients[item].lower())
                ],
                'states': [
                    {'key': key, 'label': label}
                    for key, label in payment_labels.items()
                ],
            },
            'currency': self.env.company.currency_id.name,
        }

    @api.depends(
        'amount', 'coupon_amount', 'killer_amount',
        'killer_commission', 'commission', 'taxes', 'shipping', 'other_commission'
    )
    def _compute_totals(self):
        for record in self:
            subtotal, final_total = collection_line_totals(
                amount=record.amount,
                coupon_amount=record.coupon_amount,
                killer_amount=record.killer_amount,
                killer_commission=record.killer_commission,
                commission=record.commission,
                taxes=record.taxes,
                shipping=record.shipping,
                other_commission=record.other_commission,
            )
            record.subtotal = subtotal
            record.adjusted_total = final_total
            record.amount_to_collect = final_total

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            if not self.env.user.has_group(
                    'mkp_collection_control.group_mkp_collection_operator'):
                raise AccessError(_(
                    'Se requiere el permiso Operador de Cobranza MKP.'
                ))
            return self._create_import_revisions(vals_list)
        if any(not vals.get('revision_key') for vals in vals_list):
            raise ValidationError(_('La clave de revisión es obligatoria.'))
        return super().create(vals_list)

    @api.model
    def _create_import_revisions(self, vals_list):
        revision_ids = []
        for original_values in vals_list:
            values = dict(original_values)
            sale_order = self.env['sale.order'].browse(
                values.pop('import_sale_order_id', False)
            ).exists()
            if not sale_order:
                raise ValidationError(_(
                    'Cada fila debe incluir la columna Orden de venta.'
                ))
            sale_order.read(['name', 'company_id', 'currency_id'])
            collection = self.env['mkp.collection.order'].search([
                ('sale_order_id', '=', sale_order.id)
            ], limit=1)
            if not collection:
                collection = self.env['mkp.collection.order'].sudo().create({
                    'sale_order_id': sale_order.id,
                    'marketplace': sale_order._mkp_field_as_text(
                        'x_studio_canal_de_venta_1'
                    ).strip(),
                    'marketplace_reference': sale_order._mkp_field_as_text(
                        'x_studio_nmero_de_orden_mkp'
                    ).strip(),
                })
            self._sync_sale_order(sale_order, collection)

            product_id = values.pop('product_id', False)
            sku = (values.pop('sku', '') or '').strip()
            sequence = values.pop('sequence', False)
            domain = [
                ('sale_order_id', '=', sale_order.id),
                ('is_active_revision', '=', True),
            ]
            if product_id:
                domain.append(('product_id', '=', product_id))
            if sku:
                domain.append(('sku', '=ilike', sku))
            if not product_id and not sku:
                raise ValidationError(_(
                    'La orden %s requiere Producto o SKU para identificar la línea.'
                ) % sale_order.display_name)
            if sequence:
                domain.append(('sequence', '=', sequence))
            candidates = self.search(domain)
            if not candidates:
                raise ValidationError(_(
                    'No se encontró una línea activa para la orden %s y el producto indicado.'
                ) % sale_order.display_name)
            if len(candidates) > 1:
                raise ValidationError(_(
                    'El producto aparece más de una vez en %s. Incluya la columna Secuencia.'
                ) % sale_order.display_name)

            changes = {
                field_name: values[field_name]
                for field_name in REVISION_FIELDS
                if field_name in values
            }
            if not changes:
                raise ValidationError(_(
                    'La fila no contiene campos de cobranza para actualizar.'
                ))
            revision = candidates._create_revision(
                changes,
                change_origin='import',
                comment=values.get('comment') or _('Actualización mediante importación.'),
            )
            revision_ids.append(revision.id)
        return self.browse(revision_ids)

    def write(self, vals):
        if self.env.su and self.env.context.get('mkp_internal_revision'):
            if set(vals) <= {'is_active_revision'}:
                return super().write(vals)
        raise UserError(_(
            'El historial no se modifica. Use Modificar para generar una línea nueva.'
        ))

    def unlink(self):
        raise UserError(_('Las líneas del historial de cobranza no se eliminan.'))

    @api.model
    def _sale_line_values(self, sale_line):
        product = sale_line.product_id
        return {
            'sequence': sale_line.sequence,
            'product_id': product.id or False,
            'sku': product.default_code or '',
            'product_name': (
                (sale_line.name or product.display_name or '').splitlines() or ['']
            )[0],
            'quantity': sale_line.product_uom_qty,
            'uom_name': sale_line.product_uom.name or '',
            'price_unit': sale_line.price_unit,
            'amount': sale_line.price_subtotal,
        }

    @api.model
    def _base_changed(self, history, values, sale_line):
        if history.product_id.id != values['product_id']:
            return True
        if any(history[field_name] != values[field_name]
               for field_name in ('sequence', 'sku', 'product_name', 'uom_name')):
            return True
        rounding = sale_line.product_uom.rounding or 0.01
        if float_compare(history.quantity, values['quantity'], precision_rounding=rounding):
            return True
        currency = history.currency_id
        return any(currency.compare_amounts(history[field_name], values[field_name])
                   for field_name in ('price_unit', 'amount'))

    @api.model
    def _legacy_allocations(self, collection, sale_lines):
        """Allocate existing order-level amounts once so an upgrade loses no totals."""
        allocations = {line.id: {field_name: 0.0 for field_name in MONETARY_REVISION_FIELDS}
                       for line in sale_lines}
        if not collection.initialized or not sale_lines:
            return allocations
        legacy_values = {
            'coupon_amount': collection.coupon_amount,
            'killer_amount': collection.killer_amount,
            'killer_commission': collection.killer_commission,
            'commission': collection.commission,
            'taxes': collection.withholding,
            'shipping': collection.shipping,
            'other_commission': collection.other,
        }
        total_weight = sum(abs(line.price_subtotal) for line in sale_lines)
        weights = [
            (abs(line.price_subtotal) / total_weight) if total_weight else (1 / len(sale_lines))
            for line in sale_lines
        ]
        currency = collection.currency_id
        for field_name, total in legacy_values.items():
            remaining = total
            for index, line in enumerate(sale_lines):
                value = remaining if index == len(sale_lines) - 1 else currency.round(
                    total * weights[index]
                )
                allocations[line.id][field_name] = value
                remaining = currency.round(remaining - value)
        return allocations

    @api.model
    def _sync_sale_order(self, sale_order, collection):
        sale_order.ensure_one()
        collection.ensure_one()
        if collection.sale_order_id != sale_order:
            raise ValidationError(_('La orden de venta no coincide con el expediente.'))
        self.env.cr.execute(
            'SELECT id FROM mkp_collection_order WHERE id = %s FOR UPDATE',
            [collection.id],
        )
        sale_lines = sale_order.order_line.filtered(lambda line: not line.display_type)
        active_lines = self.search([
            ('order_id', '=', collection.id),
            ('is_active_revision', '=', True),
        ])
        active_by_sale_line = {
            line.sale_line_id.id: line for line in active_lines if line.sale_line_id
        }
        allocations = self._legacy_allocations(collection, sale_lines) if not self.search_count([
            ('order_id', '=', collection.id)
        ]) else {}
        for sale_line in sale_lines:
            current = active_by_sale_line.get(sale_line.id)
            base_values = self._sale_line_values(sale_line)
            if not current:
                revision_key = 'sale.order.line:%s' % sale_line.id
                self.sudo().create({
                    'name': '%s/L%s/R01' % (
                        sale_order.name, sale_line.sequence or sale_line.id
                    ),
                    'revision_key': revision_key,
                    'revision_no': 1,
                    'is_active_revision': True,
                    'change_origin': 'initial',
                    'order_id': collection.id,
                    'sale_line_id': sale_line.id,
                    **base_values,
                    **allocations.get(sale_line.id, {}),
                })
            elif self._base_changed(current, base_values, sale_line):
                current._create_revision(
                    {}, base_values=base_values, change_origin='sale_sync',
                    comment=_('Datos sincronizados desde la línea de Ventas.')
                )
        return True

    def _create_revision(self, adjustment_values, *, base_values=None,
                         change_origin='manual', comment=''):
        self.ensure_one()
        if not self.env.user.has_group(
                'mkp_collection_control.group_mkp_collection_operator'):
            raise AccessError(_('Se requiere el permiso Operador de Cobranza MKP.'))
        unknown = set(adjustment_values) - set(REVISION_FIELDS)
        if unknown:
            raise ValidationError(_('Se intentaron modificar campos no permitidos.'))
        for field_name in MONETARY_REVISION_FIELDS:
            value = adjustment_values.get(field_name)
            if value is not None and value < 0:
                raise ValidationError(_('%s no puede ser negativo.') % self._fields[field_name].string)
        self.env.cr.execute(
            'SELECT id FROM mkp_collection_line_history WHERE id = %s FOR UPDATE',
            [self.id],
        )
        self.invalidate_recordset(['is_active_revision'])
        if not self.is_active_revision:
            raise ValidationError(_('La línea seleccionada ya no es la versión activa.'))
        effective_return_status = adjustment_values.get(
            'return_status', self.return_status
        )
        effective_return_quantity = adjustment_values.get(
            'return_quantity', self.return_quantity
        )
        try:
            validate_return_quantity(
                effective_return_quantity, self.quantity, effective_return_status
            )
        except ValueError as error:
            raise ValidationError(str(error)) from error
        values = {
            field_name: self[field_name].id
            if self._fields[field_name].type == 'many2one'
            else self[field_name]
            for field_name in BASE_FIELDS
        }
        values.update(base_values or {})
        values.update({field_name: self[field_name] for field_name in REVISION_FIELDS})
        values.update(adjustment_values)
        revision_no = self.revision_no + 1
        self.sudo().with_context(mkp_internal_revision=True).write({
            'is_active_revision': False,
        })
        return self.sudo().create({
            'name': '%s/R%02d' % (self.revision_key, revision_no),
            'revision_key': self.revision_key,
            'revision_no': revision_no,
            'previous_id': self.id,
            'is_active_revision': True,
            'change_origin': change_origin,
            'comment': comment or False,
            'order_id': self.order_id.id,
            'sale_line_id': self.sale_line_id.id or False,
            **values,
        })

    def action_edit_collection_line(self):
        self.ensure_one()
        if not self.is_active_revision:
            raise UserError(_('Solo puede modificarse la versión activa.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Modificar línea de cobranza'),
            'res_model': 'mkp.collection.line.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref(
                'mkp_collection_control.view_collection_line_wizard_form'
            ).id,
            'target': 'new',
            'context': {'default_history_id': self.id},
        }
