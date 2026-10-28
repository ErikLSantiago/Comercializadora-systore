from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class MkpCollectionImportRow(models.Model):
    _name = 'mkp.collection.import.row'
    _description = 'Registro importado de cobranza'
    _order = 'id desc'
    _rec_name = 'sale_order_id'

    sale_order_id = fields.Many2one('sale.order', string='Pedido Odoo', required=True,
                                    index=True, ondelete='restrict')
    payment_state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('recalculated', 'Recalculado'),
        ('refund', 'Devolución'),
    ], string='Estado', required=True, default='draft')
    event_time = fields.Datetime('Fecha del evento', required=True, default=fields.Datetime.now)
    gross = fields.Monetary('Venta', currency_field='currency_id')
    coupon_amount = fields.Monetary('Cupon', currency_field='currency_id')
    killer_amount = fields.Monetary('Killer', currency_field='currency_id')
    withholding = fields.Monetary('Retenciones / impuestos', currency_field='currency_id')
    commission = fields.Monetary('Comisión', currency_field='currency_id')
    killer_commission = fields.Monetary('Comisión killer', currency_field='currency_id')
    coupon_commission = fields.Monetary('Comisión cupón', currency_field='currency_id')
    shipping = fields.Monetary('Envío', currency_field='currency_id')
    other = fields.Monetary('Otras comisiones', currency_field='currency_id')
    refund_amount = fields.Monetary('Importe devolución', currency_field='currency_id')
    refund_bucket = fields.Selection([
        ('pending', 'Monto por cobrar'),
        ('held', 'Retenido'),
        ('released', 'Liberado'),
        ('paid', 'Pago reportado'),
    ], string='Origen devolución', default='pending')
    reference = fields.Char('Referencia')
    notes = fields.Text('Comentario')
    payment_amount = fields.Monetary('Pago: monto', currency_field='currency_id')
    payment_date = fields.Datetime('Pago: fecha')
    payment_status = fields.Selection([
        ('held', 'Retenido'),
        ('released', 'Liberado'),
        ('penalized', 'Penalizado'),
        ('cancelled', 'Cancelado'),
    ], string='Pago: estado')
    event_id = fields.Many2one('mkp.collection.event', string='Movimiento generado',
                               readonly=True, ondelete='restrict')
    company_id = fields.Many2one(related='sale_order_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(related='sale_order_id.currency_id', store=True, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group('mkp_collection_control.group_mkp_collection_operator'):
            raise AccessError(_('Debe pertenecer al grupo Operador de Cobranza MKP.'))
        clean_vals_list = []
        for vals in vals_list:
            clean_vals = dict(vals)
            clean_vals.pop('event_id', None)
            clean_vals_list.append(clean_vals)
        rows = super().create(clean_vals_list)
        for row in rows:
            row._publish()
        return rows

    def _publish(self):
        self.ensure_one()
        self.sale_order_id.read(['name', 'amount_total', 'company_id'])
        collection = self.env['mkp.collection.order'].search([
            ('sale_order_id', '=', self.sale_order_id.id)], limit=1)
        capture_model = self.env['mkp.collection.capture.wizard']
        if not collection:
            if self.payment_state == 'refund':
                raise ValidationError(_('La devolución requiere un expediente previo.'))
            marketplace = capture_model._get_sale_marketplace(self.sale_order_id)
            if not marketplace:
                raise ValidationError(_(
                    'La orden no tiene informado x_studio_canal_de_venta_1.'
                ))
            collection = self.env['mkp.collection.order'].sudo().create({
                'sale_order_id': self.sale_order_id.id,
                'marketplace': marketplace.strip(),
                'marketplace_reference': capture_model._get_sale_marketplace_ref(
                    self.sale_order_id
                ).strip(),
            })

        payments = []
        if self.payment_status or self.payment_date or self.payment_amount:
            if not self.payment_status or not self.payment_date:
                raise ValidationError(_(
                    'Para importar un pago indique Monto, Fecha y Estado.'
                ))
            payments.append({
                'amount': self.payment_amount,
                'payment_date': self.payment_date,
                'payment_status': self.payment_status,
            })

        event = collection._post_event(
            payment_state=self.payment_state,
            event_time=self.event_time,
            gross=self.gross,
            coupon_amount=self.coupon_amount,
            killer_amount=self.killer_amount,
            withholding=self.withholding,
            commission=self.commission,
            killer_commission=self.killer_commission,
            coupon_commission=self.coupon_commission,
            shipping=self.shipping,
            other=self.other,
            amount=self.refund_amount,
            bucket=self.refund_bucket,
            reference=self.reference or '',
            notes=self.notes or '',
            payments=payments,
        )
        self.sudo().write({'event_id': event.id})
