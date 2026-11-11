from odoo import fields, models, _
from odoo.exceptions import AccessError, ValidationError


class MkpCollectionReversalWizard(models.TransientModel):
    _name = 'mkp.collection.reversal.wizard'
    _description = 'Reversión auditada de evento financiero'

    event_id = fields.Many2one('mkp.collection.event', required=True, readonly=True)
    reason = fields.Text('Motivo de reversión', required=True)
    event_time = fields.Datetime('Fecha de la reversión', required=True,
                                 default=fields.Datetime.now)

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group('mkp_collection_control.group_mkp_collection_supervisor'):
            raise AccessError(_('Solo un supervisor puede revertir eventos.'))
        if not self.reason or not self.reason.strip():
            raise ValidationError(_('El motivo de reversión es obligatorio.'))
        event = self.event_id
        if not event or event.is_reversed or event.is_reversal_entry:
            raise ValidationError(_('El movimiento ya fue revertido o no admite reversión.'))
        payment_changes = []
        for payment in event.payment_ids:
            if not payment.is_active_revision:
                raise ValidationError(_(
                    'Revierta primero los movimientos posteriores de la cobranza %s.'
                ) % payment.payment_reference)
            restored = payment.previous_id
            payment_changes.append({
                'source_payment_id': payment.id,
                'old_amount': payment.amount,
                'old_payment_status': payment.payment_status,
                'amount': restored.amount if restored else payment.amount,
                'payment_reference': (
                    restored.payment_reference if restored else payment.payment_reference
                ),
                'payment_date': restored.payment_date if restored else payment.payment_date,
                'payment_status': restored.payment_status if restored else 'cancelled',
            })
        event.order_id._post_event(
            payment_state=event.order_id.payment_state, event_time=self.event_time,
            reference=event.reference or '', notes=_('Se revierte %s') % event.name,
            reversal_of=event, reversal_reason=self.reason.strip(),
            payments=payment_changes,
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Historial de movimientos cobranza'),
            'res_model': 'mkp.collection.event', 'view_mode': 'list,form',
            'domain': [('order_id', '=', event.order_id.id)],
        }
