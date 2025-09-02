
# -*- coding: utf-8 -*-
from odoo import api, fields, models

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    company_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Company Currency',
        readonly=True,
    )

    usd_mx = fields.Monetary(
        string='USD MX',
        currency_field='company_currency_id',
        help='Tipo de cambio: MXN por 1 USD. Se usa para calcular campos en dólares.',
        default=0.0,
    )

    currency_usd_id = fields.Many2one(
        'res.currency',
        string='USD Currency',
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False),
        help='Moneda USD utilizada para mostrar los importes en dólares.',
    )

    amount_total_usd = fields.Monetary(
        string='Total USD',
        currency_field='currency_usd_id',
        compute='_compute_amount_total_usd',
        store=False,
        readonly=True,
    )

    @api.depends('order_line.price_unit', 'order_line.product_qty', 'usd_mx')
    def _compute_amount_total_usd(self):
        for order in self:
            rate = order.usd_mx or 0.0
            total_usd = 0.0
            if rate > 0:
                for line in order.order_line:
                    total_usd += (line.price_unit / rate) * line.product_qty
            order.amount_total_usd = total_usd


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    currency_usd_id = fields.Many2one(
        'res.currency', related='order_id.currency_usd_id', readonly=True
    )

    price_unit_usd = fields.Monetary(
        string='Precio USD',
        currency_field='currency_usd_id',
        compute='_compute_usd_fields',
        store=False,
        readonly=True,
    )

    total_usd = fields.Monetary(
        string='Total USD',
        currency_field='currency_usd_id',
        compute='_compute_usd_fields',
        store=False,
        readonly=True,
    )

    @api.depends('price_unit', 'product_qty', 'order_id.usd_mx')
    def _compute_usd_fields(self):
        for line in self:
            rate = line.order_id.usd_mx or 0.0
            if rate > 0:
                pu_usd = line.price_unit / rate
                line.price_unit_usd = pu_usd
                line.total_usd = pu_usd * line.product_qty
            else:
                line.price_unit_usd = 0.0
                line.total_usd = 0.0
