from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    associated_purchase_order_ids = fields.Many2many(
        'purchase.order',
        'sale_order_purchase_order_rel',
        'sale_order_id',
        'purchase_order_id',
        string='Associated Purchase Orders',
        help='Automatic reservation for this sale will only use lots matching these purchase order numbers.',
    )
    is_wholesale_allocation = fields.Boolean(
        string='Wholesale Allocation Applies',
        compute='_compute_is_wholesale_allocation',
        store=False,
    )
    associated_purchase_order_count = fields.Integer(
        string='Associated Purchase Orders Count',
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
                    'Associated Purchase Orders can only be used on warehouses marked as Wholesale.'
                ))

    def action_view_associated_purchase_orders(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('purchase.purchase_rfq')
        action['domain'] = [('id', 'in', self.associated_purchase_order_ids.ids)]
        action['context'] = {'create': False}
        return action

    def _should_show_wholesale_po_warning(self):
        self.ensure_one()
        return bool(
            self.is_wholesale_allocation
            and not self.associated_purchase_order_ids
            and not self.env.context.get('skip_wholesale_po_warning')
        )

    def action_confirm(self):
        for order in self:
            if order._should_show_wholesale_po_warning():
                wizard = self.env['sale.order.confirm.warning'].create({
                    'sale_order_id': order.id,
                })
                return {
                    'name': _('Confirmar sin Orden de Compra asociada'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'sale.order.confirm.warning',
                    'view_mode': 'form',
                    'res_id': wizard.id,
                    'target': 'new',
                }
        return super().action_confirm()
