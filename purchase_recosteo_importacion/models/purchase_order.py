from odoo import _, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    x_exchange_rate = fields.Float(
        string='Tipo de cambio (TC)',
        digits=(16, 2),
        default=0.0,
        help='Tipo de cambio USD→MXN utilizado para convertir costos capturados en USD a MXN.',
    )

    def action_recostear(self):
        """Impacta el costo unitario calculado (MXN) a price_unit nativo."""
        for order in self:
            # Permitimos recostear incluso con mercancía recibida (según el flujo del usuario)
            # y en la práctica pueden ajustar el TC varias veces.
            if order.state == 'cancel':
                raise UserError(_('No puedes recostear una orden cancelada.'))

            if order.x_exchange_rate <= 0:
                raise UserError(_('El tipo de cambio debe ser mayor a 0 para poder recostear.'))

            for line in order.order_line:
                if line.display_type:
                    continue
                line.price_unit = line.x_calc_price_mxn or 0.0

        return True
