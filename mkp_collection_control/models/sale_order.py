from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    mkp_collection_event_count = fields.Integer('Movimientos de cobranza',
                                                 compute='_compute_mkp_collection_event_count')

    def _compute_mkp_collection_event_count(self):
        accessible = self.env.user.has_group('mkp_collection_control.group_mkp_collection_operator')
        orders = self.env['mkp.collection.order'].search([('sale_order_id', 'in', self.ids)]) if accessible else self.env['mkp.collection.order']
        counts = {o.sale_order_id.id: o.event_count for o in orders}
        for sale in self:
            sale.mkp_collection_event_count = counts.get(sale.id, 0)

    def action_open_mkp_collection(self):
        self.ensure_one()
        if not self.env.user.has_group('mkp_collection_control.group_mkp_collection_operator'):
            raise AccessError(_('No tiene permiso para consultar Cobranza MKP.'))
        collection = self.env['mkp.collection.order'].search([('sale_order_id', '=', self.id)], limit=1)
        if collection:
            return {
                'type': 'ir.actions.act_window', 'name': _('Cobranza de %s') % self.name,
                'res_model': 'mkp.collection.order', 'res_id': collection.id,
                'view_mode': 'form', 'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window', 'name': _('Iniciar cobranza de %s') % self.name,
            'res_model': 'mkp.collection.capture.wizard', 'view_mode': 'form',
            'target': 'new', 'context': {'default_sale_order_id': self.id,
                                       'default_payment_state': 'draft'},
        }
