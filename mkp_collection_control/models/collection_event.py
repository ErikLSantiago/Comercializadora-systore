from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class MkpCollectionEvent(models.Model):
    _name = 'mkp.collection.event'
    _description = 'Historial de movimientos cobranza (inalterable)'
    _order = 'event_time desc, id desc'
    _rec_name = 'name'

    name = fields.Char('Movimiento', required=True, readonly=True, index=True)
    is_active_revision = fields.Boolean('Activo', required=True, readonly=True,
                                        default=True, index=True)
    history_status = fields.Selection([
        ('active', 'Activo'),
        ('historical', 'Histórico'),
    ], string='Estatus del movimiento', compute='_compute_history_status', store=True)
    order_id = fields.Many2one('mkp.collection.order', string='Expediente de cobranza',
                                required=True, readonly=True, index=True, ondelete='restrict')
    sale_order_id = fields.Many2one(related='order_id.sale_order_id', store=True, readonly=True)
    marketplace = fields.Char(related='order_id.marketplace', store=True, readonly=True)
    marketplace_reference = fields.Char(related='order_id.marketplace_reference', store=True, readonly=True)
    currency_id = fields.Many2one(related='order_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(related='order_id.company_id', store=True, readonly=True)
    event_time = fields.Datetime('Fecha del evento MKP', required=True, readonly=True, index=True)
    event_type = fields.Selection([
        ('snapshot', 'Fotografía financiera'),
        ('opening', 'Apertura'), ('hold', 'Retenido'),
        ('unlock', 'Retenido a por cobrar'), ('release', 'Liberado'),
        ('release_direct', 'Liberado directo'), ('payment', 'Pago reportado'),
        ('coupon', 'Cupón'), ('killer', 'Killer'),
        ('commission', 'Comisión'), ('tax', 'Impuestos / retenciones'),
        ('shipping', 'Envío'), ('other', 'Otras comisiones'),
        ('refund', 'Devolución'), ('reversal', 'Reversión')],
        string='Tipo de evento', required=True, readonly=True, index=True)
    payment_state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('recalculated', 'Recalculado'),
        ('refund', 'Devolución'),
    ], string='Estado', required=True, readonly=True, index=True, default='draft')
    state_from = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('recalculated', 'Recalculado'),
        ('refund', 'Devolución'),
    ], string='Estado anterior', readonly=True)
    state_to = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('recalculated', 'Recalculado'),
        ('refund', 'Devolución'),
    ], string='Estado nuevo', readonly=True)
    is_reversal_entry = fields.Boolean('Es reversión', readonly=True, index=True)
    description = fields.Char('¿Qué pasó?', readonly=True)
    status_from = fields.Selection([
        ('none','Sin información'),('pending','Monto por cobrar'),
        ('held','Retenido'),('released','Liberado'),
        ('paid','Pago informado'),('refunded','Devoluciones')],
        string='Estado anterior', readonly=True)
    status_to = fields.Selection([
        ('none','Sin información'),('pending','Monto por cobrar'),
        ('held','Retenido'),('released','Liberado'),
        ('paid','Pago informado'),('refunded','Devoluciones')],
        string='Estado nuevo', readonly=True)
    reference = fields.Char('Referencia MKP', readonly=True, index=True)
    notes = fields.Text('Observaciones', readonly=True)
    refund_bucket = fields.Selection([
        ('pending', 'Monto por cobrar'), ('held', 'Retenido'),
        ('released', 'Liberado'), ('paid', 'Pago informado')],
        string='Origen devolución', readonly=True)
    reversal_of_id = fields.Many2one('mkp.collection.event', string='Movimiento revertido',
                                      readonly=True, ondelete='restrict')
    reversal_reason = fields.Text('Motivo de reversión', readonly=True)
    is_reversed = fields.Boolean('Revertido', compute='_compute_is_reversed')
    event_amount = fields.Monetary('Importe del evento', currency_field='currency_id', readonly=True)
    net_impact = fields.Monetary('Impacto en neto', currency_field='currency_id', readonly=True)
    refund_total_negative = fields.Monetary('Devoluciones acumuladas (negativas)',
                                            currency_field='currency_id', compute='_compute_refund_total_negative')
    refund_impact = fields.Monetary('Efecto devolución', currency_field='currency_id',
                                    compute='_compute_refund_impact')
    extra_commission = fields.Monetary('Comisión cupón / killer', currency_field='currency_id', readonly=True)
    attachment_data = fields.Binary('Evidencia', attachment=True, readonly=True, copy=False)
    attachment_name = fields.Char('Nombre de evidencia', readonly=True)
    payment_ids = fields.One2many('mkp.collection.payment', 'event_id', string='Pagos', readonly=True)
    captured_by_id = fields.Many2one(related='create_uid', string='Registrado por', readonly=True)
    captured_at = fields.Datetime(related='create_date', string='Fecha de captura', readonly=True)

    # Explicit before/after snapshots make the complete history auditable even
    # when events are backdated and subsequent changes have been entered.
    delta_gross = fields.Monetary('Δ Venta', currency_field='currency_id', readonly=True)
    delta_coupon_amount = fields.Monetary('Δ Cupon', currency_field='currency_id', readonly=True)
    delta_killer_amount = fields.Monetary('Δ Killer', currency_field='currency_id', readonly=True)
    delta_withholding = fields.Monetary('Δ Retenciones', currency_field='currency_id', readonly=True)
    delta_commission = fields.Monetary('Δ Comisión', currency_field='currency_id', readonly=True)
    delta_killer_commission = fields.Monetary('Δ Comisión killer', currency_field='currency_id', readonly=True)
    delta_coupon_commission = fields.Monetary('Δ Comisión cupón', currency_field='currency_id', readonly=True)
    delta_shipping = fields.Monetary('Δ Envío', currency_field='currency_id', readonly=True)
    delta_other = fields.Monetary('Δ Otras comisiones', currency_field='currency_id', readonly=True)
    delta_refunded = fields.Monetary('Δ Devoluciones', currency_field='currency_id', readonly=True)
    delta_pending = fields.Monetary('Δ Por cobrar', currency_field='currency_id', readonly=True)
    delta_held = fields.Monetary('Δ Retenido', currency_field='currency_id', readonly=True)
    delta_released = fields.Monetary('Δ Liberado', currency_field='currency_id', readonly=True)
    delta_paid = fields.Monetary('Δ Pago informado', currency_field='currency_id', readonly=True)

    before_gross = fields.Monetary('Antes: venta', currency_field='currency_id', readonly=True)
    before_coupon_amount = fields.Monetary('Antes: cupon', currency_field='currency_id', readonly=True)
    before_killer_amount = fields.Monetary('Antes: killer', currency_field='currency_id', readonly=True)
    before_withholding = fields.Monetary('Antes: retenciones', currency_field='currency_id', readonly=True)
    before_commission = fields.Monetary('Antes: comisión', currency_field='currency_id', readonly=True)
    before_killer_commission = fields.Monetary('Antes: comisión killer', currency_field='currency_id', readonly=True)
    before_coupon_commission = fields.Monetary('Antes: comisión cupón', currency_field='currency_id', readonly=True)
    before_shipping = fields.Monetary('Antes: envío', currency_field='currency_id', readonly=True)
    before_other = fields.Monetary('Antes: otras comisiones', currency_field='currency_id', readonly=True)
    before_refunded = fields.Monetary('Antes: devoluciones', currency_field='currency_id', readonly=True)
    before_pending = fields.Monetary('Antes: por cobrar', currency_field='currency_id', readonly=True)
    before_held = fields.Monetary('Antes: retenido', currency_field='currency_id', readonly=True)
    before_released = fields.Monetary('Antes: liberado', currency_field='currency_id', readonly=True)
    before_paid = fields.Monetary('Antes: pago informado', currency_field='currency_id', readonly=True)
    before_net = fields.Monetary('Antes: neto', currency_field='currency_id', readonly=True)
    before_sale_total = fields.Monetary('Antes: total de venta', currency_field='currency_id',
                                        compute='_compute_sale_totals')

    after_gross = fields.Monetary('Después: venta', currency_field='currency_id', readonly=True)
    after_coupon_amount = fields.Monetary('Después: cupon', currency_field='currency_id', readonly=True)
    after_killer_amount = fields.Monetary('Después: killer', currency_field='currency_id', readonly=True)
    after_withholding = fields.Monetary('Después: retenciones', currency_field='currency_id', readonly=True)
    after_commission = fields.Monetary('Después: comisión', currency_field='currency_id', readonly=True)
    after_killer_commission = fields.Monetary('Después: comisión killer', currency_field='currency_id', readonly=True)
    after_coupon_commission = fields.Monetary('Después: comisión cupón', currency_field='currency_id', readonly=True)
    after_shipping = fields.Monetary('Después: envío', currency_field='currency_id', readonly=True)
    after_other = fields.Monetary('Después: otras comisiones', currency_field='currency_id', readonly=True)
    after_refunded = fields.Monetary('Después: devoluciones', currency_field='currency_id', readonly=True)
    after_pending = fields.Monetary('Después: por cobrar', currency_field='currency_id', readonly=True)
    after_held = fields.Monetary('Después: retenido', currency_field='currency_id', readonly=True)
    after_released = fields.Monetary('Después: liberado', currency_field='currency_id', readonly=True)
    after_paid = fields.Monetary('Después: pago informado', currency_field='currency_id', readonly=True)
    after_net = fields.Monetary('Después: neto', currency_field='currency_id', readonly=True)
    after_sale_total = fields.Monetary('Después: total de venta', currency_field='currency_id',
                                       compute='_compute_sale_totals')

    _sql_constraints = [
        ('unique_reversal_original', 'unique(reversal_of_id)',
         'Este movimiento ya tiene una reversión registrada.'),
    ]

    @api.depends('is_active_revision')
    def _compute_history_status(self):
        for rec in self:
            rec.history_status = 'active' if rec.is_active_revision else 'historical'

    @api.depends('after_refunded')
    def _compute_refund_total_negative(self):
        for rec in self:
            rec.refund_total_negative = -rec.after_refunded

    @api.depends('before_gross', 'before_coupon_amount', 'before_killer_amount',
                 'after_gross', 'after_coupon_amount', 'after_killer_amount')
    def _compute_sale_totals(self):
        for rec in self:
            rec.before_sale_total = (
                rec.before_gross - rec.before_coupon_amount + rec.before_killer_amount
            )
            rec.after_sale_total = (
                rec.after_gross - rec.after_coupon_amount + rec.after_killer_amount
            )

    @api.depends('delta_refunded')
    def _compute_refund_impact(self):
        for rec in self:
            rec.refund_impact = -rec.delta_refunded

    @api.depends('reversal_of_id')
    def _compute_is_reversed(self):
        original_ids = self.ids
        reversions = self.sudo().search([('reversal_of_id', 'in', original_ids)]) if original_ids else self.browse()
        reversed_ids = set(reversions.mapped('reversal_of_id').ids)
        for rec in self:
            rec.is_reversed = rec.id in reversed_ids

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_('Use el formulario de Captura de cobranza para registrar un evento.'))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.su and self.env.context.get('mkp_internal_revision'):
            if set(vals) <= {'is_active_revision'}:
                return super().write(vals)
        raise UserError(_('El historial de movimientos es inalterable. Use Revertir.'))

    def unlink(self):
        raise UserError(_('Los movimientos de cobranza no se eliminan. Use Revertir.'))

    def action_reverse(self):
        self.ensure_one()
        if not self.env.user.has_group('mkp_collection_control.group_mkp_collection_supervisor'):
            raise AccessError(_('Solo un supervisor puede solicitar reversiones.'))
        if self.is_reversal_entry or self.is_reversed:
            raise UserError(_('No se puede revertir este movimiento.'))
        return {
            'type': 'ir.actions.act_window', 'name': _('Revertir evento financiero'),
            'res_model': 'mkp.collection.reversal.wizard', 'view_mode': 'form',
            'target': 'new', 'context': {'default_event_id': self.id},
        }
