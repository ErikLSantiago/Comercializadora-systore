from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .ledger import KEYS, event_deltas, snapshot_deltas, apply_event, money, net


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
    payment_state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('recalculated', 'Recalculado'),
        ('refund', 'Devolución'),
    ], string='Estado', default='draft', required=True, readonly=True, index=True)
    event_ids = fields.One2many('mkp.collection.event', 'order_id', string='Historial')
    event_count = fields.Integer('Movimientos', compute='_compute_event_count')

    gross = fields.Monetary('Venta ajustada', currency_field='currency_id', readonly=True)
    coupon_amount = fields.Monetary('Cupon', currency_field='currency_id', readonly=True)
    killer_amount = fields.Monetary('Killer', currency_field='currency_id', readonly=True)
    sale_total = fields.Monetary('Total de venta', currency_field='currency_id',
                                 compute='_compute_sale_total', store=True)
    withholding = fields.Monetary('Retenciones / impuestos', currency_field='currency_id', readonly=True)
    commission = fields.Monetary('Comisiones', currency_field='currency_id', readonly=True)
    killer_commission = fields.Monetary('Comisión killer', currency_field='currency_id', readonly=True)
    coupon_commission = fields.Monetary('Comisión cupón', currency_field='currency_id', readonly=True)
    shipping = fields.Monetary('Envío', currency_field='currency_id', readonly=True)
    other = fields.Monetary('Otras comisiones', currency_field='currency_id', readonly=True)
    refunded = fields.Monetary('Devoluciones acumuladas', currency_field='currency_id', readonly=True)
    refund_impact = fields.Monetary('Devoluciones (impacto)', compute='_compute_refund_impact', store=True,
                                    currency_field='currency_id')
    net_expected = fields.Monetary('Neto ajustado de cobranza', currency_field='currency_id', readonly=True)
    amount_to_collect = fields.Monetary(related='net_expected', string='Monto a cobrar',
                                        currency_field='currency_id', readonly=True, store=True)
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

    @api.depends('gross', 'coupon_amount', 'killer_amount')
    def _compute_sale_total(self):
        for rec in self:
            rec.sale_total = rec.gross + rec.coupon_amount + rec.killer_amount

    @api.depends('event_ids')
    def _compute_event_count(self):
        counts = self.env['mkp.collection.event']._read_group(
            [('order_id', 'in', self.ids)], ['order_id'], ['__count']) if self.ids else []
        mapping = {record.id: qty for record, qty in counts}
        for order in self:
            order.event_count = mapping.get(order.id, 0)

    def write(self, vals):
        locked_fields = set(KEYS) | {'net_expected', 'initialized', 'payment_state', 'sale_order_id',
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

    def _post_event(self, *, payment_state, event_time, reference='', notes='', amount=0,
                    gross=0, coupon_amount=0, killer_amount=0,
                    withholding=0, commission=0,
                    killer_commission=0, coupon_commission=0,
                    shipping=0, other=0, bucket='pending',
                    attachment_data=False, attachment_name=False,
                    reversal_of=None, reversal_reason=''):
        """Lock, validate and post one immutable state change atomically."""
        self.ensure_one()
        self._check_operator()
        self.env.cr.execute('SELECT id FROM mkp_collection_order WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset(list(KEYS) + ['net_expected', 'initialized', 'payment_state'])
        before = self._snapshot()
        was_initialized = self.initialized
        previous_payment_state = self.payment_state or 'draft'

        if reversal_of:
            if not self.env.user.has_group('mkp_collection_control.group_mkp_collection_supervisor'):
                raise AccessError(_('Solo el supervisor puede revertir eventos.'))
            if reversal_of.order_id != self or reversal_of.is_reversal_entry:
                raise ValidationError(_('El evento de origen no es válido.'))
            if self.env['mkp.collection.event'].sudo().search_count([
                ('reversal_of_id', '=', reversal_of.id)]):
                raise ValidationError(_('Este evento ya fue revertido.'))
            deltas = {key: -money(reversal_of['delta_' + key]) for key in KEYS}
            technical_kind = 'reversal'
            target_payment_state = previous_payment_state
        else:
            target_payment_state = payment_state
            if target_payment_state not in ('draft', 'confirmed', 'recalculated', 'refund'):
                raise ValidationError(_('Seleccione un estado de cobranza válido.'))
            if target_payment_state == 'refund' and not self.initialized:
                raise ValidationError(_('Primero debe registrar el desglose de comisiones.'))
            try:
                if target_payment_state == 'refund':
                    technical_kind = 'refund'
                    deltas = event_deltas('refund', amount=amount, bucket=bucket)
                else:
                    technical_kind = 'snapshot'
                    deltas = snapshot_deltas(
                        before,
                        gross=gross,
                        coupon_amount=coupon_amount,
                        killer_amount=killer_amount,
                        withholding=withholding,
                        commission=commission,
                        killer_commission=killer_commission,
                        coupon_commission=coupon_commission,
                        shipping=shipping,
                        other=other,
                    )
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
            if (target_payment_state == 'refund' and bucket == 'pending'
                    and before['pending'] < money(amount)):
                raise ValidationError(_('No existe suficiente monto por cobrar para la devolución.'))

        try:
            after = apply_event(before, deltas)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        new_initialized = self.initialized
        if not reversal_of and target_payment_state != 'refund':
            new_initialized = True
        elif reversal_of and reversal_of.event_type in ('opening', 'snapshot'):
            new_initialized = any(after[key] != 0 for key in KEYS)

        vals = {key: float(after[key]) for key in KEYS}
        vals.update(
            net_expected=float(net(after)),
            initialized=new_initialized,
            payment_state=target_payment_state,
        )
        self.sudo().write(vals)

        labels = {
            'draft': _('Borrador'),
            'confirmed': _('Confirmado'),
            'recalculated': _('Recalculado'),
            'refund': _('Devolución'),
        }
        if reversal_of:
            primary_amount = -money(reversal_of.event_amount)
        elif target_payment_state == 'refund':
            primary_amount = money(amount)
        else:
            primary_amount = money(gross)

        if reversal_of:
            previous_status, next_status = reversal_of.status_to, reversal_of.status_from
        elif target_payment_state == 'refund':
            previous_status, next_status = bucket, 'refunded'
        else:
            previous_status, next_status = ('none' if not was_initialized else 'pending'), 'pending'

        event_vals = {
            'name': self.env['ir.sequence'].sudo().next_by_code('mkp.collection.event') or _('Nuevo'),
            'order_id': self.id,
            'event_type': technical_kind,
            'payment_state': target_payment_state,
            'state_from': previous_payment_state if was_initialized else False,
            'state_to': target_payment_state,
            'is_reversal_entry': bool(reversal_of),
            'description': _('Reversión') if reversal_of else labels[target_payment_state],
            'status_from': previous_status,
            'status_to': next_status,
            'event_time': event_time,
            'reference': reference,
            'notes': notes,
            'refund_bucket': bucket if target_payment_state == 'refund' and not reversal_of else False,
            'reversal_of_id': reversal_of.id if reversal_of else False,
            'reversal_reason': reversal_reason,
            'extra_commission': 0.0,
            'event_amount': float(primary_amount),
            'net_impact': float(net(after) - net(before)),
            'attachment_data': attachment_data or False,
            'attachment_name': attachment_name or False,
            **{'delta_' + key: float(deltas[key]) for key in KEYS},
            **{'before_' + key: float(before[key]) for key in KEYS},
            **{'after_' + key: float(after[key]) for key in KEYS},
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
                'default_payment_state': 'draft' if not self.initialized else self.payment_state,
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
