from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class MkpWholesalePayment(models.Model):
    _name = 'mkp.wholesale.payment'
    _description = 'Pago general de orden de mayoreo'
    _order = 'payment_date desc, id desc'
    _rec_name = 'payment_reference'

    sale_order_id = fields.Many2one(
        'sale.order', string='Orden de venta', required=True, index=True,
        ondelete='restrict'
    )
    company_id = fields.Many2one(
        related='sale_order_id.company_id', store=True, readonly=True
    )
    currency_id = fields.Many2one(
        related='sale_order_id.currency_id', store=True, readonly=True
    )
    payment_date = fields.Date(
        'Fecha de pago', required=True, default=fields.Date.context_today,
        index=True
    )
    payment_reference = fields.Char(
        'Referencia de pago', required=True, index=True
    )
    amount = fields.Monetary(
        'Importe', required=True, currency_field='currency_id'
    )
    payment_status = fields.Selection([
        ('held', 'Retenido'),
        ('pending', 'Pendiente'),
        ('paid', 'Pagado'),
        ('cancelled', 'Cancelado'),
        ('refund', 'Reembolso'),
    ], string='Estado', required=True, default='pending', index=True)
    notes = fields.Char('Comentario')

    _sql_constraints = [
        (
            'positive_wholesale_payment_amount',
            'CHECK(amount > 0)',
            'El importe del pago de mayoreo debe ser mayor a cero.',
        ),
    ]

    def _check_operator(self):
        if not self.env.su and not self.env.user.has_group(
                'mkp_collection_control.group_mkp_collection_operator'):
            raise AccessError(_(
                'Se requiere el permiso Operador de Cobranza MKP.'
            ))

    @api.constrains('sale_order_id')
    def _check_wholesale_order(self):
        for payment in self:
            if payment.sale_order_id.mkp_collection_type != 'wholesale':
                raise ValidationError(_(
                    'Los pagos generales solo se registran en órdenes de tipo Mayoreo.'
                ))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_operator()
        payments = super().create(vals_list)
        if not self.env.context.get('mkp_skip_wholesale_log'):
            labels = dict(self._fields['payment_status']._description_selection(self.env))
            for payment in payments:
                payment.sale_order_id.message_post(body=Markup(
                    '<p><strong>%s</strong></p>'
                    '<p>%s: %s · %s: %s · %s: %s</p>'
                ) % (
                    escape(_('Pago de mayoreo registrado')),
                    escape(_('Referencia')), escape(payment.payment_reference),
                    escape(_('Importe')), escape(payment.amount),
                    escape(_('Estado')), escape(labels.get(
                        payment.payment_status, payment.payment_status
                    )),
                ))
        return payments

    def write(self, vals):
        self._check_operator()
        if 'sale_order_id' in vals:
            raise UserError(_('La orden de un pago de mayoreo no puede cambiar.'))
        tracked_fields = {
            'payment_date', 'payment_reference', 'amount', 'payment_status', 'notes'
        }
        before = {
            payment.id: {
                field_name: payment[field_name]
                for field_name in tracked_fields if field_name in vals
            }
            for payment in self
        }
        result = super().write(vals)
        if not self.env.context.get('mkp_skip_wholesale_log'):
            labels = dict(self._fields['payment_status']._description_selection(self.env))
            field_labels = {
                'payment_date': _('Fecha de pago'),
                'payment_reference': _('Referencia'),
                'amount': _('Importe'),
                'payment_status': _('Estado'),
                'notes': _('Comentario'),
            }
            for payment in self:
                changes = []
                for field_name, old_value in before[payment.id].items():
                    new_value = payment[field_name]
                    if old_value == new_value:
                        continue
                    if field_name == 'payment_status':
                        old_value = labels.get(old_value, old_value or '')
                        new_value = labels.get(new_value, new_value or '')
                    changes.append('%s: %s → %s' % (
                        field_labels[field_name], old_value or '-', new_value or '-'
                    ))
                if changes:
                    payment.sale_order_id.message_post(body=Markup(
                        '<p><strong>%s</strong> · %s</p><p>%s</p>'
                    ) % (
                        escape(_('Pago de mayoreo modificado')),
                        escape(payment.payment_reference),
                        escape(' · '.join(changes)),
                    ))
        return result

    def unlink(self):
        raise UserError(_(
            'Los pagos de mayoreo no se eliminan. Cambie su estado a Cancelado.'
        ))
