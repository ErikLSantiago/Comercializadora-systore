from odoo import _, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    x_exchange_rate = fields.Float(
        string='Tipo de cambio',
        digits=(16, 6),
        default=0.0,
        help='Tipo de cambio USD→MXN utilizado para convertir costos capturados en USD a MXN.',
    )

    def action_recostear(self):
        """Impacta el costo unitario calculado (MXN) a price_unit nativo."""
        for order in self:
            if order.state in ('done', 'cancel'):
                raise UserError(_('No puedes recostear una orden en estado %s.') % order.state)

            if order.x_exchange_rate <= 0:
                raise UserError(_('El tipo de cambio debe ser mayor a 0 para poder recostear.'))

            # Evitar recosteo si ya hay recepción validada (para no alterar valuación histórica)
            received_lines = order.order_line.filtered(lambda l: not l.display_type and (l.qty_received or 0) > 0)
            if received_lines:
                raise UserError(_(
                    'No se puede recostear porque ya hay líneas con cantidad recibida.\n'
                    'Crea una nueva orden o realiza un ajuste contable según tu flujo.'
                ))

            for line in order.order_line:
                if line.display_type:
                    continue
                line.price_unit = line.x_calc_price_mxn or 0.0

        return True
