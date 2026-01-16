# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    company_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda de la compañía',
        related='company_id.currency_id',
        readonly=True,
        store=False,
    )

    x_import_fixed_mxn = fields.Monetary(
        string='Costo fijo de importación (MXN)',
        currency_field='company_currency_id',
        default=0.0,
        help='Costo fijo unitario de importación en moneda de la compañía (típicamente MXN). Se copia a las líneas de compra al seleccionar el producto.',
    )
