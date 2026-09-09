from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    associated_purchase_order_ids = fields.Many2many(
        'purchase.order',
        'sale_order_purchase_order_rel',
        'sale_order_id',
        'purchase_order_id',
        string='Órdenes de compra asociadas',
        help=(
            'La reserva automática de esta venta sólo utilizará lotes cuyo nombre '
            'coincida con los números de las órdenes de compra asociadas.'
        ),
    )
    is_wholesale_allocation = fields.Boolean(
        string='Aplica Wholesale Allocation',
        compute='_compute_is_wholesale_allocation',
        store=False,
    )
    associated_purchase_order_count = fields.Integer(
        string='Cantidad de órdenes de compra asociadas',
        compute='_compute_associated_purchase_order_count',
    )

    @api.depends('associated_purchase_order_ids')
    def _compute_associated_purchase_order_count(self):
        for order in self:
            order.associated_purchase_order_count = len(order.associated_purchase_order_ids)

    @api.depends('warehouse_id', 'warehouse_id.is_wholesale')
    def _compute_is_wholesale_allocation(self):
        for order in self:
            order.is_wholesale_allocation = bool(order.warehouse_id.is_wholesale)

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id_clear_associated_purchase_orders(self):
        for order in self:
            if not order.is_wholesale_allocation:
                order.associated_purchase_order_ids = [(5, 0, 0)]

    @api.constrains('associated_purchase_order_ids', 'warehouse_id')
    def _check_associated_purchase_orders(self):
        for order in self:
            if not order.is_wholesale_allocation and order.associated_purchase_order_ids:
                raise ValidationError(_(
                    'Las Órdenes de Compra asociadas sólo pueden utilizarse en almacenes marcados como Wholesale.'
                ))

    def action_view_associated_purchase_orders(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('purchase.purchase_rfq')
        action['domain'] = [('id', 'in', self.associated_purchase_order_ids.ids)]
        action['context'] = {'create': False}
        return action

    def action_confirm(self):
        """Require an associated PO when the wholesale warehouse requests it."""
        for order in self:
            warehouse = order.warehouse_id
            if (
                warehouse
                and warehouse.is_wholesale
                and warehouse.require_wholesale_associated_po
                and not order.associated_purchase_order_ids
            ):
                raise UserError(_(
                    'Debe vincular al menos una Orden de Compra asociada antes de confirmar esta venta.'
                ))
        return super().action_confirm()
