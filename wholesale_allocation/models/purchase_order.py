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
        copy=False,
        help='Órdenes de venta que tienen vinculada esta Orden de Compra mediante Wholesale Allocation. No se copian al duplicar la Orden de Compra.',
    )
    associated_sale_order_count = fields.Integer(
        string='Ventas asociadas',
        compute='_compute_associated_sale_order_count',
    )
    wholesale_allocation_applicable = fields.Boolean(
        string='Aplica Wholesale Allocation',
        compute='_compute_wholesale_assignment_status',
    )
    wholesale_assignment_status = fields.Selection(
        [
            ('unassigned', 'Sin asignar'),
            ('assigned', 'Asignada'),
        ],
        string='Asignación Wholesale',
        compute='_compute_wholesale_assignment_status',
        help=(
            'Indica si esta Orden de Compra, cuando está dirigida a un almacén Wholesale, '
            'ya fue vinculada a por lo menos una Orden de Venta.'
        ),
    )

    @api.depends('associated_sale_order_ids')
    def _compute_associated_sale_order_count(self):
        for order in self:
            order.associated_sale_order_count = len(order.associated_sale_order_ids)

    @api.depends(
        'associated_sale_order_ids',
        'picking_type_id',
        'picking_type_id.warehouse_id',
        'picking_type_id.warehouse_id.is_wholesale',
    )
    def _compute_wholesale_assignment_status(self):
        for order in self:
            warehouse = order.picking_type_id.warehouse_id
            applicable = bool(warehouse and warehouse.is_wholesale)
            order.wholesale_allocation_applicable = applicable
            if not applicable:
                order.wholesale_assignment_status = False
            elif order.associated_sale_order_ids:
                order.wholesale_assignment_status = 'assigned'
            else:
                order.wholesale_assignment_status = 'unassigned'

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
