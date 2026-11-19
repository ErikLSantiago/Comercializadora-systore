from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class MkpCollectionLinePaymentDetail(models.Model):
    _name = 'mkp.collection.line.payment.detail'
    _description = 'Pago parcial de línea de cobranza'
    _order = 'payment_date, id'
    _rec_name = 'payment_reference'

    history_id = fields.Many2one(
        'mkp.collection.line.history', string='Revisión de cobranza',
        required=True, readonly=True, index=True, ondelete='restrict'
    )
    order_id = fields.Many2one(
        related='history_id.order_id', store=True, readonly=True
    )
    sale_order_id = fields.Many2one(
        related='history_id.sale_order_id', store=True, readonly=True, index=True
    )
    sale_line_id = fields.Many2one(
        related='history_id.sale_line_id', store=True, readonly=True, index=True
    )
    product_name = fields.Char(
        related='history_id.product_name', store=True, readonly=True
    )
    payment_date = fields.Date(
        'Fecha de pago parcial', required=True, readonly=True, index=True
    )
    amount = fields.Monetary(
        'Importe pagado', required=True, readonly=True,
        currency_field='currency_id'
    )
    payment_reference = fields.Char(
        'Referencia de pago', required=True, readonly=True, index=True
    )
    currency_id = fields.Many2one(
        related='history_id.currency_id', store=True, readonly=True
    )
    company_id = fields.Many2one(
        related='history_id.company_id', store=True, readonly=True
    )
    captured_by_id = fields.Many2one(
        related='create_uid', string='Registrado por', store=True, readonly=True
    )
    captured_at = fields.Datetime(
        related='create_date', string='Fecha de registro', store=True, readonly=True
    )
    registered_by_id = fields.Many2one(
        'res.users', string='Registrado originalmente por', readonly=True,
        index=True
    )
    registered_at = fields.Datetime(
        'Fecha original de registro', readonly=True, index=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_(
                'Los pagos parciales solo pueden guardarse desde Cobranza.'
            ))
        prepared_values = []
        for original_values in vals_list:
            values = dict(original_values)
            if (values.get('amount') or 0) <= 0:
                raise ValidationError(_('El importe pagado debe ser mayor a cero.'))
            if not (values.get('payment_reference') or '').strip():
                raise ValidationError(_('La referencia de pago es obligatoria.'))
            values.setdefault('registered_by_id', self.env.user.id)
            values.setdefault('registered_at', fields.Datetime.now())
            prepared_values.append(values)
        return super().create(prepared_values)

    def write(self, vals):
        raise UserError(_(
            'El historial de pagos no se modifica; guarde una nueva revisión de cobranza.'
        ))

    def unlink(self):
        raise UserError(_('Los pagos históricos no se eliminan.'))
