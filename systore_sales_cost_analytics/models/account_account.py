# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = 'account.account'

    systore_sales_channel_id = fields.Many2one('systore.sales.channel', string='Canal de venta Systore', index=True)

    systore_analytics_type = fields.Selection([
        ('sale', 'Venta'),
        ('transit_return', 'Tránsito / devolución bruta'),
        ('other', 'Otro'),
    ], string='Clasificación Systore', default='other', index=True,
       help='Clasificación analítica. Si queda en Otro, Systore detecta automáticamente Tránsito como Devolución y Clientes como Venta por el nombre de la cuenta.')
