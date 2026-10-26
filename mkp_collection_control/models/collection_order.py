from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .ledger import KEYS, event_deltas, apply_event, money, net


class MkpCollectionOrder(models.Model):
    _name = 'mkp.collection.order'
    _description = 'Cobranza de orden marketplace'
    _order = 'id desc'
    _rec_name = 'sale_order_id'

    sale_order_id = fields.Many2one('sale.order', string='Orden de venta', required=True,
                                    index=True, ondelete='restrict', readonly=True)
    company_id = fields.Many2one(related='sale_order_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(related='sale_order_id.currency_id', store=True, readonly=True)
    marketplace = fields.Char('Marketplace', readonly=True)
    marketplace_reference = fields.Char('Número de orden MKP', readonly=True, index=True)
    sale_amount = fields.Monetary(related='sale_order_id.amount_total', string='Importe de Odoo',
                                  currency_field='currency_id', readonly=True)
    initialized = fields.Boolean('Cobranza inicializada', default=False, readonly=True)
    event_ids = fields.One2many('mkp.collection.event', 'order_id', string='Historial')
    event_count = fields.Integer('Movimientos', compute='_compute_event_count')

    gross = fields.Monetary('Venta ajustada', currency_field='currency_id', readonly=True)
    withholding = fields.Monetary('Retenciones / impuestos', currency_field='currency_id', readonly=True)
    commission = fields.Monetary('Comisiones', currency_field='currency_id', readonly=True)
    shipping = fields.Monetary('Envío', currency_field='currency_id', readonly=True)
    other = fields.Monetary('Otras comisiones', currency_field='currency_id', readonly=True)
    refunded = fields.Monetary('Devoluciones acumuladas', currency_field='currency_id', readonly=True)
    refund_impact = fields.Monetary('Devoluciones (impacto)', compute='_compute_refund_impact', store=True,
                                    currency_field='currency_id')
    net_expected = fields.Monetary('Neto ajustado de cobranza', currency_field='currency_id', readonly=True)
    pending = fields.Monetary('Monto por cobrar', currency_field='currency_id', readonly=True)
    held = fields.Monetary('Retenido', currency_field='currency_id', readonly=True)
    released = fields.Monetary('Liberado', currency_field='currency_id', readonly=True)
    paid = fields.Monetary('Pagado reportado (no bancario)', currency_field='currency_id', readonly=True)

    _sql_constraints = [
        ('uniq_sale_order_collection', 'unique(sale_order_id)',
         'La orden de venta solo puede tener un expediente de cobranza.'),
    ]

    @api.depends('refunded')
    def _compute_refund_impact(self):
        for rec in self:
            rec.refund_impact = -rec.refunded

    @api.depends('event_ids')
    def _compute_event_count(self):
        counts = self.env['mkp.collection.event']._read_group(
            [('order_id', 'in', self.ids)], ['order_id'], ['__count']) if self.ids else []
        mapping = {record.id: qty for record, qty in counts}
        for order in self:
            order.event_count = mapping.get(order.id, 0)

    def write(self, vals):
        locked_fields = set(KEYS) | {'net_expected', 'initialized', 'sale_order_id',
                                     'marketplace', 'marketplace_reference'}
        if locked_fields.intersection(vals) and not self.env.su:
            raise AccessError(_('Los importes de cobranza solo pueden cambiar al confirmar eventos.'))
        return super().write(vals)

    def unlink(self):
        raise UserError(_('Los expedientes de cobranza no se pueden eliminar.'))

    def _check_operator(self):
        if not self.env.user.has_group('mkp_collection_control.group_mkp_collection_operator'):
            raise AccessError(_('Se requiere el permiso Operador de Cobranza MKP.'))

    def _snapshot(self):
        self.ensure_one()
        return {k: money(self[k]) for k in KEYS}

    def _post_event(self, *, kind, event_time, reference='', notes='', amount=0,
                    extra_commission=0, gross=0, withholding=0,
                    commission=0, shipping=0, other=0, bucket='pending',
                    attachment_data=False, attachment_name=False,
                    reversal_of=None, reversal_reason=''):
        """The only application entrypoint. Lock, validate, post and snapshot atomically."""
        self.ensure_one()
        self._check_operator()
        # The DB lock ensures a second operator sees fresh totals before posting.
        self.env.cr.execute('SELECT id FROM mkp_collection_order WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset(list(KEYS) + ['net_expected', 'initialized'])
        before = self._snapshot()
        if reversal_of:
            if not self.env.user.has_group('mkp_collection_control.group_mkp_collection_supervisor'):
                raise AccessError(_('Solo el supervisor puede revertir eventos.'))
            if reversal_of.order_id != self or reversal_of.event_type == 'reversal':
                raise ValidationError(_('El evento de origen no es válido.'))
            if self.env['mkp.collection.event'].sudo().search_count([
                ('reversal_of_id', '=', reversal_of.id)]):
                raise ValidationError(_('Este evento ya fue revertido.'))
            deltas = {k: -money(reversal_of['delta_' + k]) for k in KEYS}
            kind = 'reversal'
        else:
            if kind == 'opening' and self.initialized:
                raise ValidationError(_('Este pedido ya tiene desglose inicial.'))
            if kind != 'opening' and not self.initialized:
                raise ValidationError(_('Primero debe registrar el desglose inicial.'))
            try:
                deltas = event_deltas(kind, amount=amount,
                                      extra_commission=extra_commission, gross=gross,
                                      withholding=withholding, commission=commission,
                                      shipping=shipping, other=other, bucket=bucket)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
            if kind in ('hold', 'release_direct') and before['pending'] < money(amount):
                raise ValidationError(_('El monto por cobrar es insuficiente para este evento.'))
            if kind == 'refund' and bucket == 'pending' and before['pending'] < money(amount):
                raise ValidationError(_('No existe suficiente monto por cobrar para la devolución.'))
        try:
            after = apply_event(before, deltas)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        # An opening cannot be reversed while another active event remains.
        new_initialized = self.initialized
        if kind == 'opening':
            new_initialized = True
        elif kind == 'reversal' and reversal_of.event_type == 'opening':
            if any(after[k] != 0 for k in KEYS):
                raise ValidationError(_('Revierta primero los movimientos posteriores antes de anular el inicio.'))
            new_initialized = False
        vals = {k: float(after[k]) for k in KEYS}
        vals.update(net_expected=float(net(after)), initialized=new_initialized)
        self.sudo().write(vals)
        labels = dict(opening='Apertura de cobranza', hold='Retención',
                      unlock='Liberación de retención a pendiente',
                      release='Liberación de fondos', release_direct='Liberación directa',
                      payment='Pago informado por MKP', coupon='Cupón confirmado',
                      killer='Killer confirmado', commission='Ajuste de comisión',
                      tax='Ajuste de impuestos / retenciones',
                      shipping='Ajuste de envío', other='Otras comisiones',
                      refund='Devolución financiera', reversal='Reversión')
        if reversal_of:
            primary_amount = -money(reversal_of.event_amount)
        elif kind == 'opening':
            primary_amount = money(gross)
        else:
            primary_amount = money(amount)
        status_map = {
            'opening': ('none', 'pending'),
            'hold': ('pending', 'held'), 'unlock': ('held', 'pending'),
            'release': ('held', 'released'), 'release_direct': ('pending', 'released'),
            'payment': ('released', 'paid'),
            'coupon': ('pending', 'pending'), 'killer': ('pending', 'pending'),
            'commission': ('pending', 'pending'), 'tax': ('pending', 'pending'),
            'shipping': ('pending', 'pending'), 'other': ('pending', 'pending'),
            'refund': (bucket, 'refunded'),
        }
        previous_status, next_status = (
            (reversal_of.status_to, reversal_of.status_from) if reversal_of
            else status_map[kind]
        )
        event_vals = {
            'name': self.env['ir.sequence'].sudo().next_by_code('mkp.collection.event') or _('Nuevo'),
            'order_id': self.id,
            'event_type': kind,
            'description': labels[kind],
            'status_from': previous_status,
            'status_to': next_status,
            'event_time': event_time,
            'reference': reference,
            'notes': notes,
            'refund_bucket': bucket if kind == 'refund' else False,
            'reversal_of_id': reversal_of.id if reversal_of else False,
            'reversal_reason': reversal_reason,
            'extra_commission': float(money(extra_commission)) if kind in ('coupon', 'killer') else 0.0,
            'event_amount': float(primary_amount),
            'net_impact': float(net(after) - net(before)),
            'attachment_data': attachment_data or False,
            'attachment_name': attachment_name or False,
            **{'delta_' + k: float(deltas[k]) for k in KEYS},
            **{'before_' + k: float(before[k]) for k in KEYS},
            **{'after_' + k: float(after[k]) for k in KEYS},
            'before_net': float(net(before)),
            'after_net': float(net(after)),
        }
        return self.env['mkp.collection.event'].sudo().create(event_vals)

    def action_new_event(self):
        self.ensure_one()
        self._check_operator()
        return {
            'type': 'ir.actions.act_window', 'name': _('Capturar movimiento de cobranza'),
            'res_model': 'mkp.collection.capture.wizard', 'view_mode': 'form',
            'target': 'new', 'context': {
                'default_order_id': self.id,
                'default_sale_order_id': self.sale_order_id.id,
                'default_event_type': 'opening' if not self.initialized else 'hold',
            },
        }

    def action_view_events(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Historial de movimientos cobranza'),
            'res_model': 'mkp.collection.event', 'view_mode': 'list,form',
            'domain': [('order_id', '=', self.id)],
            'context': {'default_order_id': self.id},
        }
