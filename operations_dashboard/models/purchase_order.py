from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    systore_expected_packages = fields.Integer(
        string='Cajas esperadas', default=0, tracking=True,
        help='Cantidad informativa de cajas de esta compra. No representa paquetes de inventario.',
    )
    systore_operations_pieces = fields.Float(
        string='Piezas de la compra', digits='Product Unit of Measure',
        compute='_compute_systore_operations_pieces', store=True,
        help='Total solicitado de productos físicos, convertido a la unidad de inventario de cada producto.',
    )

    @api.depends('order_line.product_qty', 'order_line.display_type',
                 'order_line.product_id', 'order_line.product_id.type',
                 'order_line.product_id.uom_id', 'order_line.product_id.uom_id.factor',
                 'order_line.product_uom', 'order_line.product_uom.factor')
    def _compute_systore_operations_pieces(self):
        for order in self:
            order.systore_operations_pieces = sum(
                line.product_uom._compute_quantity(line.product_qty, line.product_id.uom_id, round=False)
                for line in order.order_line
                if not line.display_type and line.product_id and line.product_id.type != 'service'
            )

    @api.constrains('systore_expected_packages')
    def _check_systore_expected_packages(self):
        if any(order.systore_expected_packages < 0 for order in self):
            raise ValidationError(_('Las cajas esperadas no pueden ser negativos.'))
