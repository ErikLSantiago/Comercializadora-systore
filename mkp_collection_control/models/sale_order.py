from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    mkp_collection_event_count = fields.Integer('Líneas de cobranza',
                                                 compute='_compute_mkp_collection_event_count')
    mkp_return_count = fields.Integer(
        'Devoluciones', compute='_compute_mkp_return_count'
    )

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
            })
        else:
            synchronization = {}
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
