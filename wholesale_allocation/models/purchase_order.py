from odoo import api, fields, models, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    associated_sale_order_ids = fields.Many2many(
        'sale.order',
        'sale_order_purchase_order_rel',
        'purchase_order_id',
        'sale_order_id',
        string='Ventas asociadas',
        readonly=True,
        help='Órdenes de venta que tienen vinculada esta Orden de Compra mediante Wholesale Allocation.',
    )
    associated_sale_order_count = fields.Integer(
        string='Ventas asociadas',
        compute='_compute_associated_sale_order_count',
    )

    @api.depends('associated_sale_order_ids')
    def _compute_associated_sale_order_count(self):
        for order in self:
            order.associated_sale_order_count = len(order.associated_sale_order_ids)

    def action_view_associated_sale_orders(self):
        self.ensure_one()
        return {
            'name': _('Ventas asociadas'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.associated_sale_order_ids.ids)],
            'context': {'create': False},
        }
