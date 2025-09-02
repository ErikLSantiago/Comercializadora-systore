
from odoo import models, fields, api

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    company_currency_id = fields.Many2one(
        'res.currency',
        string='Company Currency',
        related='company_id.currency_id',
        readonly=True,
        store=True,
    )
    currency_usd_id = fields.Many2one(
        'res.currency',
        string='USD Currency',
        default=lambda self: self.env.ref('base.USD'),
        readonly=True,
        store=True,
    )
    usd_mx = fields.Monetary(
        string='USD MX',
        currency_field='company_currency_id',
        help='Tipo de cambio MXN por 1 USD.'
    )
    amount_total_usd = fields.Monetary(
        string='Total USD',
        currency_field='currency_usd_id',
        compute='_compute_amount_total_usd',
        store=True,
        readonly=True,
    )

    @api.depends('order_line.price_total_usd')
    def _compute_amount_total_usd(self):
        for order in self:
            order.amount_total_usd = sum(order.order_line.mapped('price_total_usd'))


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    currency_usd_id = fields.Many2one(
        'res.currency',
        string='USD Currency',
        related='order_id.currency_usd_id',
        readonly=True,
        store=True,
    )
    price_unit_usd = fields.Monetary(
        string='Precio USD',
        currency_field='currency_usd_id',
        compute='_compute_usd_fields',
        store=True,
        readonly=True,
    )
    price_total_usd = fields.Monetary(
        string='Total USD',
        currency_field='currency_usd_id',
        compute='_compute_usd_fields',
        store=True,
        readonly=True,
    )

    @api.depends('price_unit', 'product_qty', 'order_id.usd_mx')
    def _compute_usd_fields(self):
        for line in self:
            rate = line.order_id.usd_mx or 0.0
            unit_usd = (line.price_unit / rate) if rate else 0.0
            line.price_unit_usd = unit_usd
            line.price_total_usd = unit_usd * (line.product_qty or 0.0)
