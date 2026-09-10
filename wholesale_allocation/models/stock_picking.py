from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    associated_purchase_order_ids = fields.Many2many(
        'purchase.order',
        compute='_compute_associated_purchase_order_ids',
        string='Associated Purchase Orders',
        help='Purchase orders allowed for automatic reservation in this picking.',
    )
    is_wholesale_allocation = fields.Boolean(
        compute='_compute_is_wholesale_allocation',
        string='Wholesale Allocation Applies',
    )
    allowed_lot_ids = fields.Many2many(
        'stock.lot',
        compute='_compute_allowed_lot_ids',
        string='Allowed Lots for Auto Reservation',
    )
    allowed_lot_names_display = fields.Char(
        compute='_compute_allowed_lot_names_display',
        string='Allowed Lot Names',
    )

    @api.depends('sale_id', 'sale_id.associated_purchase_order_ids')
    def _compute_associated_purchase_order_ids(self):
        for picking in self:
            picking.associated_purchase_order_ids = picking.sale_id.associated_purchase_order_ids

    @api.depends('sale_id', 'sale_id.is_wholesale_allocation')
    def _compute_is_wholesale_allocation(self):
        for picking in self:
            picking.is_wholesale_allocation = bool(
                picking.sale_id and picking.sale_id.is_wholesale_allocation
            )

    @api.depends('associated_purchase_order_ids')
    def _compute_allowed_lot_ids(self):
        lot_model = self.env['stock.lot']
        for picking in self:
            if picking.is_wholesale_allocation and picking.associated_purchase_order_ids:
                picking.allowed_lot_ids = lot_model.search([
                    ('name', 'in', picking.associated_purchase_order_ids.mapped('name'))
                ])
            else:
                picking.allowed_lot_ids = False

    @api.depends('associated_purchase_order_ids')
    def _compute_allowed_lot_names_display(self):
        for picking in self:
            picking.allowed_lot_names_display = ', '.join(picking.associated_purchase_order_ids.mapped('name'))
