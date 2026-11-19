from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    mkp_collection_type = fields.Selection([
        ('marketplace', 'Marketplace'),
        ('wholesale', 'Mayoreo'),
    ], string='Tipo de cobranza', required=True, default='marketplace', copy=False)

    mkp_collection_event_count = fields.Integer('Líneas de cobranza',
                                                 compute='_compute_mkp_collection_event_count')
    mkp_return_count = fields.Integer(
        'Devoluciones', compute='_compute_mkp_return_count'
    )
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
    mkp_wholesale_paid = fields.Monetary(
        'Importe pagado', currency_field='currency_id',
        compute='_compute_mkp_wholesale_totals', compute_sudo=True,
        groups='mkp_collection_control.group_mkp_collection_operator'
    )
    mkp_wholesale_amount_to_collect = fields.Monetary(
        'Por cobrar', currency_field='currency_id',
        compute='_compute_mkp_wholesale_totals', compute_sudo=True,
        groups='mkp_collection_control.group_mkp_collection_operator'
    )

    def write(self, vals):
        if 'mkp_collection_type' in vals:
            new_type = vals['mkp_collection_type'] or 'marketplace'
            changing_orders = self.filtered(
                lambda sale: sale.mkp_collection_type != new_type
            )
            if changing_orders:
                collections = self.env['mkp.collection.order'].search([
                    ('sale_order_id', 'in', changing_orders.ids),
                ])
                if collections and self.env['mkp.collection.line.history'].search_count([
                    ('order_id', 'in', collections.ids),
                ]):
                    raise UserError(_(
                        'El Tipo de cobranza no puede cambiar después de generar '
                        'el historial de la orden.'
                    ))
        return super().write(vals)

    def _compute_mkp_wholesale_totals(self):
        histories = self.env['mkp.collection.line.history'].sudo().search([
            ('sale_order_id', 'in', self.ids),
            ('is_active_revision', '=', True),
            ('collection_type', '=', 'wholesale'),
        ]) if self.ids else self.env['mkp.collection.line.history']
        active_by_order = {
            history.sale_order_id.id: history for history in histories
        }
        for sale in self:
            history = active_by_order.get(sale.id)
            sale.mkp_wholesale_adjusted_total = history.adjusted_total if history else 0
            sale.mkp_wholesale_commissions = (
                history.killer_commission_total
                + history.commission_total
                + history.other_commission_total
            ) if history else 0
            sale.mkp_wholesale_taxes = history.taxes if history else 0
            sale.mkp_wholesale_shipping = history.shipping if history else 0
            sale.mkp_wholesale_paid = history.paid_amount if history else 0
            sale.mkp_wholesale_amount_to_collect = history.amount_to_collect if history else 0

    def _compute_mkp_collection_event_count(self):
        accessible = self.env.user.has_group('mkp_collection_control.group_mkp_collection_operator')
        grouped = self.env['mkp.collection.line.history']._read_group(
            [('sale_order_id', 'in', self.ids), ('is_active_revision', '=', True)],
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
                'collection_type': self.mkp_collection_type or 'marketplace',
            })
        else:
            synchronization = {}
            requested_type = self.mkp_collection_type or 'marketplace'
            if collection.collection_type != requested_type:
                if self.env['mkp.collection.line.history'].search_count([
                    ('order_id', '=', collection.id),
                ]):
                    raise UserError(_(
                        'El Tipo de cobranza no puede cambiar después de generar '
                        'el historial. Cree la cobranza con el tipo correcto.'
                    ))
                synchronization['collection_type'] = requested_type
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
            'domain': [('sale_order_id', '=', self.id)],
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
