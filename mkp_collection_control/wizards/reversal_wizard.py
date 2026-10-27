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
        event.order_id._post_event(
            payment_state=event.order_id.payment_state, event_time=self.event_time,
            reference=event.reference or '', notes=_('Se revierte %s') % event.name,
            reversal_of=event, reversal_reason=self.reason.strip(),
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Historial de movimientos cobranza'),
            'res_model': 'mkp.collection.event', 'view_mode': 'list,form',
            'domain': [('order_id', '=', event.order_id.id)],
        }
