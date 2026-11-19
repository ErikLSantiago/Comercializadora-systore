from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .ledger import wholesale_order_totals


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    mkp_collection_type = fields.Selection([
        ('marketplace', 'Marketplace'),
        ('wholesale', 'Mayoreo'),
    ], string='Tipo de venta', required=True, default='marketplace', copy=False,
       tracking=True)
    mkp_collection_event_count = fields.Integer('Líneas de cobranza',
                                                 compute='_compute_mkp_collection_event_count')
    mkp_return_count = fields.Integer(
        'Devoluciones', compute='_compute_mkp_return_count'
    )
    mkp_wholesale_general_expense = fields.Monetary(
        'Gasto general', currency_field='currency_id', default=0, copy=False,
        tracking=True,
        help='Importe general que se descuenta del total de la orden de mayoreo.'
    )
    mkp_wholesale_expense_note = fields.Char(
        'Referencia del gasto', copy=False, tracking=True
    )
    mkp_wholesale_payment_ids = fields.One2many(
        'mkp.wholesale.payment', 'sale_order_id', string='Pagos mayoreo', copy=False
    )
    mkp_wholesale_net_expected = fields.Monetary(
        'Neto esperado', currency_field='currency_id',
        compute='_compute_mkp_wholesale_totals', compute_sudo=True,
        groups='mkp_collection_control.group_mkp_collection_operator'
    )
    mkp_wholesale_paid = fields.Monetary(
        'Importe pagado', currency_field='currency_id',
        compute='_compute_mkp_wholesale_totals', compute_sudo=True,
        groups='mkp_collection_control.group_mkp_collection_operator'
    )
    mkp_wholesale_pending = fields.Monetary(
        'Pagos pendientes o retenidos', currency_field='currency_id',
        compute='_compute_mkp_wholesale_totals', compute_sudo=True,
        groups='mkp_collection_control.group_mkp_collection_operator'
    )
    mkp_wholesale_amount_to_collect = fields.Monetary(
        'Por cobrar', currency_field='currency_id',
        compute='_compute_mkp_wholesale_totals', compute_sudo=True,
        groups='mkp_collection_control.group_mkp_collection_operator'
    )
    # Compatibility aliases retained because the database can still render the
    # 18.0.1.0.20 inherited view before the module upgrade replaces that view.
    mkp_wholesale_adjusted_total = fields.Monetary(
        'Total ajustado', currency_field='currency_id',
        compute='_compute_mkp_wholesale_totals', compute_sudo=True,
        groups='mkp_collection_control.group_mkp_collection_operator'
    )
    mkp_wholesale_commissions = fields.Monetary(
        'Comisiones totales', currency_field='currency_id',
        compute='_compute_mkp_wholesale_totals', compute_sudo=True,
        groups='mkp_collection_control.group_mkp_collection_operator'
    )
    mkp_wholesale_taxes = fields.Monetary(
        'Impuestos', currency_field='currency_id',
        compute='_compute_mkp_wholesale_totals', compute_sudo=True,
        groups='mkp_collection_control.group_mkp_collection_operator'
    )
    mkp_wholesale_shipping = fields.Monetary(
        'Envío', currency_field='currency_id',
        compute='_compute_mkp_wholesale_totals', compute_sudo=True,
        groups='mkp_collection_control.group_mkp_collection_operator'
    )

    @api.depends(
        'amount_total', 'mkp_wholesale_general_expense',
        'mkp_wholesale_payment_ids.amount',
        'mkp_wholesale_payment_ids.payment_status',
    )
    def _compute_mkp_wholesale_totals(self):
        self.env.cr.execute("""
            SELECT
                to_regclass('mkp_wholesale_payment') IS NOT NULL,
                EXISTS (
                    SELECT 1
                      FROM information_schema.columns
                     WHERE table_schema = current_schema()
                       AND table_name = 'sale_order'
                       AND column_name = 'mkp_wholesale_general_expense'
                )
        """)
        payment_table_ready, expense_column_ready = self.env.cr.fetchone()
        schema_ready = payment_table_ready and expense_column_ready

        legacy_by_sale = {}
        if not schema_ready and self.ids:
            legacy_histories = self.env[
                'mkp.collection.line.history'
            ].sudo().search([
                ('sale_order_id', 'in', self.ids),
                ('is_active_revision', '=', True),
                ('collection_type', '=', 'wholesale'),
                ('sale_line_id', '=', False),
            ], order='revision_no desc, id desc')
            for history in legacy_histories:
                legacy_by_sale.setdefault(history.sale_order_id.id, history)

        for sale in self:
            history = legacy_by_sale.get(sale.id)
            if schema_ready:
                net_expected, paid, pending, balance = wholesale_order_totals(
                    order_total=sale.amount_total,
                    general_expense=sale.mkp_wholesale_general_expense,
                    payments=[{
                        'amount': payment.amount,
                        'payment_status': payment.payment_status,
                    } for payment in sale.mkp_wholesale_payment_ids],
                )
                commissions = sale.mkp_wholesale_general_expense
                taxes = 0
                shipping = 0
            else:
                net_expected = history.adjusted_total if history else 0
                paid = history.paid_amount if history else 0
                pending = 0
                balance = history.amount_to_collect if history else 0
                commissions = (
                    history.killer_commission_total
                    + history.commission_total
                    + history.other_commission_total
                ) if history else 0
                taxes = history.taxes if history else 0
                shipping = history.shipping if history else 0
            sale.mkp_wholesale_net_expected = net_expected
            sale.mkp_wholesale_paid = paid
            sale.mkp_wholesale_pending = pending
            sale.mkp_wholesale_amount_to_collect = balance
            sale.mkp_wholesale_adjusted_total = net_expected
            sale.mkp_wholesale_commissions = commissions
            sale.mkp_wholesale_taxes = taxes
            sale.mkp_wholesale_shipping = shipping

    @api.constrains('mkp_wholesale_general_expense')
    def _check_mkp_wholesale_general_expense(self):
        if any(sale.mkp_wholesale_general_expense < 0 for sale in self):
            raise ValidationError(_('El Gasto general no puede ser negativo.'))

    def write(self, vals):
        if 'mkp_collection_type' in vals:
            new_type = vals['mkp_collection_type'] or 'marketplace'
            changing_orders = self.filtered(
                lambda sale: sale.mkp_collection_type != new_type
            )
            if new_type == 'wholesale' and changing_orders:
                collections = self.env['mkp.collection.order'].search([
                    ('sale_order_id', 'in', changing_orders.ids),
                ])
                if collections and self.env['mkp.collection.line.history'].search_count([
                    ('order_id', 'in', collections.ids),
                    ('sale_line_id', '!=', False),
                ]):
                    raise UserError(_(
                        'Una orden con historial de Cobranza Marketplace no puede '
                        'cambiarse a Mayoreo.'
                    ))
            if new_type == 'marketplace' and any(
                sale.mkp_wholesale_payment_ids
                or sale.mkp_wholesale_general_expense
                for sale in changing_orders
            ):
                raise UserError(_(
                    'Una orden con pagos o gasto general de Mayoreo no puede '
                    'cambiarse a Marketplace.'
                ))
            if new_type == 'marketplace' and changing_orders:
                legacy_wholesale = self.env['mkp.collection.order'].search([
                    ('sale_order_id', 'in', changing_orders.ids),
                    ('collection_type', '=', 'wholesale'),
                ])
                if legacy_wholesale and self.env[
                        'mkp.collection.line.history'].search_count([
                            ('order_id', 'in', legacy_wholesale.ids),
                        ]):
                    raise UserError(_(
                        'La orden conserva movimientos generales de Mayoreo de '
                        'una versión anterior y no puede cambiarse a Marketplace.'
                    ))
        return super().write(vals)

    def _compute_mkp_collection_event_count(self):
        accessible = self.env.user.has_group('mkp_collection_control.group_mkp_collection_operator')
        grouped = self.env['mkp.collection.line.history']._read_group(
            [
                ('sale_order_id', 'in', self.ids),
                ('is_active_revision', '=', True),
                ('collection_type', '=', 'marketplace'),
            ],
            ['sale_order_id'], ['__count']
        ) if accessible and self.ids else []
        counts = {sale_order.id: quantity for sale_order, quantity in grouped}
        for sale in self:
            sale.mkp_collection_event_count = counts.get(sale.id, 0)

    def _compute_mkp_return_count(self):
        accessible = self.env.user.has_group(
            'mkp_collection_control.group_mkp_collection_operator'
        )
        grouped = self.env['mkp.collection.line.history']._read_group(
            [
                ('sale_order_id', 'in', self.ids),
                ('is_active_revision', '=', True),
                ('collection_type', '=', 'marketplace'),
                ('return_status', '!=', 'sale'),
            ],
            ['sale_order_id'], ['__count']
        ) if accessible and self.ids else []
        counts = {sale_order.id: quantity for sale_order, quantity in grouped}
        for sale in self:
            sale.mkp_return_count = counts.get(sale.id, 0)

    def action_open_mkp_collection(self):
        self.ensure_one()
        if not self.env.user.has_group('mkp_collection_control.group_mkp_collection_operator'):
            raise AccessError(_('No tiene permiso para consultar Cobranza MKP.'))
        if self.mkp_collection_type != 'marketplace':
            raise UserError(_(
                'Las órdenes de Mayoreo se gestionan en la pestaña Pagos mayoreo.'
            ))
        collection = self.env['mkp.collection.order'].search([
            ('sale_order_id', '=', self.id)
        ], limit=1)
        marketplace = self._mkp_field_as_text('x_studio_canal_de_venta_1').strip()
        marketplace_reference = self._mkp_field_as_text(
            'x_studio_nmero_de_orden_mkp'
        ).strip()
        if not collection:
            collection = self.env['mkp.collection.order'].sudo().create({
                'sale_order_id': self.id,
                'marketplace': marketplace,
                'marketplace_reference': marketplace_reference,
                'collection_type': 'marketplace',
            })
        else:
            synchronization = {}
            if collection.collection_type != 'marketplace':
                if self.env['mkp.collection.line.history'].search_count([
                    ('order_id', '=', collection.id),
                ]):
                    raise UserError(_(
                        'La orden conserva un historial anterior de Mayoreo. '
                        'Revise su Tipo de venta antes de abrir Cobranza.'
                    ))
                synchronization['collection_type'] = 'marketplace'
            if collection.marketplace != marketplace:
                synchronization['marketplace'] = marketplace
            if collection.marketplace_reference != marketplace_reference:
                synchronization['marketplace_reference'] = marketplace_reference
            if synchronization:
                collection.sudo().write(synchronization)
        self.env['mkp.collection.line.history']._sync_sale_order(self, collection)
        action = self.env.ref(
            'mkp_collection_control.action_collection_line_history'
        ).read()[0]
        action.update({
            'name': _('Cobranza de %s') % self.name,
            'domain': [
                ('sale_order_id', '=', self.id),
                ('collection_type', '=', 'marketplace'),
            ],
            'context': {'default_sale_order_id': self.id},
        })
        return action

    def _mkp_field_as_text(self, field_name):
        self.ensure_one()
        if field_name not in self._fields or not self[field_name]:
            return ''
        value = self[field_name]
        if hasattr(value, 'display_name'):
            return value.display_name or ''
        field = self._fields[field_name]
        if field.type == 'selection':
            return dict(field._description_selection(self.env)).get(value, str(value))
        return str(value)

    def action_open_mkp_returns(self):
        self.ensure_one()
        if not self.env.user.has_group(
                'mkp_collection_control.group_mkp_collection_operator'):
            raise AccessError(_('No tiene permiso para consultar devoluciones MKP.'))
        action = self.env.ref(
            'mkp_collection_control.action_collection_line_history'
        ).read()[0]
        action.update({
            'name': _('Devoluciones de %s') % self.name,
            'domain': [
                ('sale_order_id', '=', self.id),
                ('is_active_revision', '=', True),
                ('collection_type', '=', 'marketplace'),
                ('return_status', '!=', 'sale'),
            ],
            'context': {'default_sale_order_id': self.id},
        })
        return action


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    mkp_commission = fields.Monetary(
        'Comisiones', currency_field='currency_id',
        compute='_compute_mkp_collection_amounts', compute_sudo=True,
        groups='mkp_collection_control.group_mkp_collection_operator'
    )
    mkp_shipping = fields.Monetary(
        'Envío', currency_field='currency_id',
        compute='_compute_mkp_collection_amounts', compute_sudo=True,
        groups='mkp_collection_control.group_mkp_collection_operator'
    )
    mkp_withholding = fields.Monetary(
        'Retenciones', currency_field='currency_id',
        compute='_compute_mkp_collection_amounts', compute_sudo=True,
        groups='mkp_collection_control.group_mkp_collection_operator'
    )
    mkp_other_commission = fields.Monetary(
        'Otras comisiones', currency_field='currency_id',
        compute='_compute_mkp_collection_amounts', compute_sudo=True,
        groups='mkp_collection_control.group_mkp_collection_operator'
    )

    def _compute_mkp_collection_amounts(self):
        histories = self.env['mkp.collection.line.history'].sudo().search([
            ('sale_line_id', 'in', self.ids),
            ('is_active_revision', '=', True),
        ]) if self.ids else self.env['mkp.collection.line.history']
        active_by_line = {
            history.sale_line_id.id: history
            for history in histories if history.sale_line_id
        }
        for line in self:
            history = active_by_line.get(line.id)
            line.mkp_commission = history.commission_total if history else 0
            line.mkp_shipping = history.shipping if history else 0
            line.mkp_withholding = history.taxes if history else 0
            line.mkp_other_commission = history.other_commission_total if history else 0
