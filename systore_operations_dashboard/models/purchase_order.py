from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    systore_expected_packages = fields.Integer(
        string='Bultos esperados', default=0, tracking=True,
        help='Cantidad informativa de cajas o bultos de esta compra. No representa paquetes de inventario.',
    )

    @api.constrains('systore_expected_packages')
    def _check_systore_expected_packages(self):
        if any(order.systore_expected_packages < 0 for order in self):
            raise ValidationError(_('Los bultos esperados no pueden ser negativos.'))
