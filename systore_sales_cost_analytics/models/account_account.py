# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = 'account.account'

    systore_sales_channel_id = fields.Many2one(
        'systore.sales.channel',
        string='Canal de venta',
        index=True,
        help='Canal utilizado por Analítica de ventas para segmentar esta cuenta contable.',
    )
