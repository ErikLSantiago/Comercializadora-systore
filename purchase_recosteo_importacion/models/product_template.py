from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_import_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda importación',
        related='company_id.currency_id',
        readonly=True,
    )

    x_import_fixed_mxn = fields.Monetary(
        string='Costo fijo de importación (MXN)',
        currency_field='x_import_currency_id',
        help='Costo unitario fijo de importación en pesos mexicanos. Se copia a la línea de compra al seleccionar el producto.',
        digits=(16, 2),
        default=0.0,
    )
