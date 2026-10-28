from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class MkpCollectionPayment(models.Model):
    _name = 'mkp.collection.payment'
    _description = 'Pago de cobranza marketplace'
    _order = 'payment_date desc, id desc'

    name = fields.Char('Pago', required=True, readonly=True, index=True)
    order_id = fields.Many2one('mkp.collection.order', required=True, readonly=True,
                               index=True, ondelete='restrict')
    event_id = fields.Many2one('mkp.collection.event', required=True, readonly=True,
                               index=True, ondelete='restrict')
    payment_date = fields.Datetime('Fecha', required=True, readonly=True, index=True)
    payment_status = fields.Selection([
        ('held', 'Retenido'),
        ('released', 'Liberado'),
        ('penalized', 'Penalizado'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', required=True, readonly=True, index=True)
    amount = fields.Monetary('Monto', required=True, readonly=True,
                             currency_field='currency_id')
    currency_id = fields.Many2one(related='order_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(related='order_id.company_id', store=True, readonly=True)
    captured_by_id = fields.Many2one(related='create_uid', string='Registrado por', readonly=True)
    captured_at = fields.Datetime(related='create_date', string='Fecha de captura', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_('Los pagos solo pueden registrarse desde la captura de cobranza.'))
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(_('Los pagos históricos no se modifican. Registre un nuevo movimiento.'))

    def unlink(self):
        raise UserError(_('Los pagos históricos no se eliminan.'))
