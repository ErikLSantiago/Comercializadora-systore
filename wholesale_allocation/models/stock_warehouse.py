from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    is_wholesale = fields.Boolean(
        string='Wholesale',
        help='Activa la lógica de Wholesale Allocation para este almacén.'
    )
    require_wholesale_associated_po = fields.Boolean(
        string='Exigir OC asociada al confirmar ventas',
        default=True,
        help=(
            'Si está activo, las órdenes de venta de este almacén no podrán confirmarse '
            'sin al menos una Orden de Compra en el campo Órdenes de compra asociadas.'
        ),
    )
