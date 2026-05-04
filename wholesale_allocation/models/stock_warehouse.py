from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    is_wholesale = fields.Boolean(
        string='Wholesale',
        help='Enable wholesale allocation logic for this warehouse.'
    )
