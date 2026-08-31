# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = 'account.account'

    systore_analytics_type = fields.Selection([
        ('sale', 'Venta'),
        ('transit_return', 'Tránsito / devolución bruta'),
        ('other', 'Otro'),
    ], string='Clasificación Systore', default='other', index=True,
       help='Clasificación analítica. Las cuentas de Tránsito pueden usarse como segmentador de devoluciones brutas.')
