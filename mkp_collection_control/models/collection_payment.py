from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class MkpCollectionPayment(models.Model):
    _name = 'mkp.collection.payment'
    _description = 'Pago de cobranza marketplace'
    _order = 'payment_date desc, id desc'

    name = fields.Char('Pago', required=True, readonly=True, index=True)
    revision_key = fields.Char('Clave de cobranza', readonly=True, index=True)
    revision_no = fields.Integer('Revisión', required=True, readonly=True, default=1)
    previous_id = fields.Many2one('mkp.collection.payment', string='Revisión anterior',
                                  readonly=True, ondelete='restrict')
    is_active_revision = fields.Boolean('Activo', required=True, readonly=True,
                                        default=True, index=True)
    history_status = fields.Selection([
        ('active', 'Activo'),
        ('historical', 'Histórico'),
    ], string='Estatus del movimiento', compute='_compute_history_status')
    order_id = fields.Many2one('mkp.collection.order', required=True, readonly=True,
                               index=True, ondelete='restrict')
    event_id = fields.Many2one('mkp.collection.event', required=True, readonly=True,
                               index=True, ondelete='restrict')
    sale_order_id = fields.Many2one(related='order_id.sale_order_id', store=True, readonly=True)
    marketplace = fields.Char(related='order_id.marketplace', store=True, readonly=True)
    marketplace_reference = fields.Char(related='order_id.marketplace_reference',
                                         store=True, readonly=True)
    payment_date = fields.Datetime('Fecha', required=True, readonly=True, index=True)
    payment_reference = fields.Char('Referencia de pago', readonly=True, index=True)
    payment_status = fields.Selection([
        ('held', 'Retenido'),
        ('pending', 'Pendiente'),
        ('paid', 'Pagado'),
        ('cancelled', 'Cancelado'),
        ('refund', 'Reembolso'),
    ], string='Estado', required=True, readonly=True, index=True)
    amount = fields.Monetary('Importe', required=True, readonly=True,
                             currency_field='currency_id')
    currency_id = fields.Many2one(related='order_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(related='order_id.company_id', store=True, readonly=True)
    captured_by_id = fields.Many2one(related='create_uid', string='Registrado por', readonly=True)
    captured_at = fields.Datetime(related='create_date', string='Fecha de captura', readonly=True)

    _sql_constraints = [
        ('unique_collection_revision', 'unique(revision_key, revision_no)',
         'La revisión de cobranza ya existe.'),
    ]

    @api.depends('is_active_revision')
    def _compute_history_status(self):
        for rec in self:
            rec.history_status = 'active' if rec.is_active_revision else 'historical'

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_('Los pagos solo pueden registrarse desde la captura de cobranza.'))
        if any(not vals.get('revision_key') or not vals.get('payment_reference')
               for vals in vals_list):
            raise UserError(_('La clave y la referencia de cobranza son obligatorias.'))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.su and self.env.context.get('mkp_internal_revision'):
            if set(vals) <= {'is_active_revision'}:
                return super().write(vals)
        raise UserError(_('Los pagos históricos no se modifican. Registre un nuevo movimiento.'))

    def unlink(self):
        raise UserError(_('Los pagos históricos no se eliminan.'))
