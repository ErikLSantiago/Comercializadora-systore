# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Convertir la pasarela única anterior en una línea de pago."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    SaleOrder = env['sale.order'].with_context(active_test=False)
    PaymentLine = env['mkp.sale.gateway.payment']

    orders = SaleOrder.search([
        ('mkp_payment_gateway_config_id', '!=', False),
        ('amount_total', '>', 0),
        ('mkp_gateway_payment_line_ids', '=', False),
    ])
    for order in orders:
        PaymentLine.create({
            'order_id': order.id,
            'gateway_config_id': order.mkp_payment_gateway_config_id.id,
            'payment_amount': order.amount_total,
        })
