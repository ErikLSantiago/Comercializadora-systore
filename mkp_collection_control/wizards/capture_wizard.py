from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class MkpCollectionCaptureWizard(models.TransientModel):
    _name = 'mkp.collection.capture.wizard'
    _description = 'Captura manual de eventos de cobranza'

    sale_order_id = fields.Many2one('sale.order', string='Orden de venta', required=True)
    order_id = fields.Many2one('mkp.collection.order', string='Expediente de cobranza', readonly=True)
    marketplace = fields.Char('Marketplace', readonly=True)
    marketplace_reference = fields.Char('Número de orden MKP', readonly=True)
    payment_state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('recalculated', 'Recalculado'),
        ('refund', 'Devolución'),
    ], string='Estado', required=True, default='draft')
    event_time = fields.Datetime('Fecha y hora del evento', required=True,
                                 default=fields.Datetime.now)
    gross = fields.Monetary('Venta', currency_field='currency_id')
    coupon_amount = fields.Monetary('Cupon', currency_field='currency_id')
    killer_amount = fields.Monetary('Killer', currency_field='currency_id')
    sale_total = fields.Monetary('Total de venta', currency_field='currency_id',
                                 compute='_compute_totals')
    withholding = fields.Monetary('Retenciones / impuestos', currency_field='currency_id')
    commission = fields.Monetary('Comisión', currency_field='currency_id')
    killer_commission = fields.Monetary('Comisión killer', currency_field='currency_id')
    coupon_commission = fields.Monetary('Comisión cupón', currency_field='currency_id')
    shipping = fields.Monetary('Envío', currency_field='currency_id')
    other = fields.Monetary('Otras comisiones', currency_field='currency_id')
    refunded = fields.Monetary('Devoluciones acumuladas', currency_field='currency_id', readonly=True)
    amount_to_collect = fields.Monetary('Monto a cobrar', currency_field='currency_id',
                                        compute='_compute_totals')
    amount = fields.Monetary('Importe del evento', currency_field='currency_id')
    refund_bucket = fields.Selection([
        ('pending', 'Monto por cobrar'), ('held', 'Retenido'),
        ('released', 'Liberado'), ('paid', 'Pago reportado')],
        string='¿De qué saldo se descuenta?', default='pending')
    currency_id = fields.Many2one(related='sale_order_id.currency_id', readonly=True)
    reference = fields.Char('Referencia del reporte / marketplace')
    notes = fields.Text('Comentario')
    attachment_data = fields.Binary('Evidencia del movimiento', attachment=False)
    attachment_name = fields.Char('Nombre del archivo')

    @api.depends('gross', 'coupon_amount', 'killer_amount', 'withholding',
                 'commission', 'killer_commission', 'coupon_commission',
                 'shipping', 'other', 'refunded')
    def _compute_totals(self):
        for wizard in self:
            wizard.sale_total = wizard.gross + wizard.coupon_amount + wizard.killer_amount
            wizard.amount_to_collect = (
                wizard.sale_total - wizard.withholding - wizard.commission
                - wizard.killer_commission - wizard.coupon_commission
                - wizard.shipping - wizard.other - wizard.refunded
            )

    @api.model
    def default_get(self, field_names):
        vals = super().default_get(field_names)
        sale_id = vals.get('sale_order_id') or self.env.context.get('default_sale_order_id')
        order_id = vals.get('order_id') or self.env.context.get('default_order_id')
        if order_id:
            existing = self.env['mkp.collection.order'].browse(order_id)
            if existing.exists():
                sale_id = existing.sale_order_id.id
                vals['sale_order_id'] = sale_id
                vals['marketplace'] = existing.marketplace
                vals['marketplace_reference'] = existing.marketplace_reference
                vals['payment_state'] = existing.payment_state if existing.initialized else 'draft'
                for field_name in ('gross', 'coupon_amount', 'killer_amount',
                                   'withholding', 'commission',
                                   'killer_commission', 'coupon_commission',
                                   'shipping', 'other'):
                    vals[field_name] = existing[field_name]
                vals['refunded'] = existing.refunded
        if sale_id:
            sale = self.env['sale.order'].browse(sale_id)
            if sale.exists():
                vals.setdefault('gross', sale.amount_total)
                vals['marketplace'] = self._get_sale_marketplace(sale)
                vals['marketplace_reference'] = self._get_sale_marketplace_ref(sale)
        return vals

    @api.model
    def _field_as_text(self, sale, field_name):
        if field_name not in sale._fields or not sale[field_name]:
            return ''
        value = sale[field_name]
        if hasattr(value, 'display_name'):
            return value.display_name or ''
        field = sale._fields[field_name]
        if field.type == 'selection':
            return dict(field._description_selection(sale.env)).get(value, str(value))
        return str(value)

    @api.model
    def _get_sale_marketplace(self, sale):
        return self._field_as_text(sale, 'x_studio_canal_de_venta_1')

    @api.model
    def _get_sale_marketplace_ref(self, sale):
        return self._field_as_text(sale, 'x_studio_nmero_de_orden_mkp')

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        if self.sale_order_id:
            existing = self.env['mkp.collection.order'].search([
                ('sale_order_id', '=', self.sale_order_id.id)], limit=1)
            self.order_id = existing
            self.marketplace = self._get_sale_marketplace(self.sale_order_id)
            self.marketplace_reference = self._get_sale_marketplace_ref(self.sale_order_id)
            if existing:
                self.payment_state = existing.payment_state if existing.initialized else 'draft'
                self.gross = existing.gross
                self.coupon_amount = existing.coupon_amount
                self.killer_amount = existing.killer_amount
                self.withholding = existing.withholding
                self.commission = existing.commission
                self.killer_commission = existing.killer_commission
                self.coupon_commission = existing.coupon_commission
                self.shipping = existing.shipping
                self.other = existing.other
                self.refunded = existing.refunded
            else:
                self.payment_state = 'draft'
                self.gross = self.sale_order_id.amount_total
                self.coupon_amount = 0
                self.killer_amount = 0
                self.withholding = 0
                self.commission = 0
                self.killer_commission = 0
                self.coupon_commission = 0
                self.shipping = 0
                self.other = 0
                self.refunded = 0

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group('mkp_collection_control.group_mkp_collection_operator'):
            raise AccessError(_('Debe pertenecer al grupo Operador de Cobranza MKP.'))
        if not self.sale_order_id.exists():
            raise ValidationError(_('Seleccione una orden válida.'))
        # Read with caller's rights: never use sudo to bypass sale.order security.
        self.sale_order_id.read(['name', 'amount_total', 'company_id'])
        marketplace = self._get_sale_marketplace(self.sale_order_id)
        marketplace_reference = self._get_sale_marketplace_ref(self.sale_order_id)
        existing = self.env['mkp.collection.order'].search([
            ('sale_order_id', '=', self.sale_order_id.id)], limit=1)
        if not existing:
            if self.payment_state == 'refund':
                raise ValidationError(_('Primero registre el desglose de comisiones.'))
            if not marketplace or not marketplace.strip():
                raise ValidationError(_(
                    'La orden no tiene informado el campo x_studio_canal_de_venta_1.'
                ))
            existing = self.env['mkp.collection.order'].sudo().create({
                'sale_order_id': self.sale_order_id.id,
                'marketplace': marketplace.strip(),
                'marketplace_reference': (marketplace_reference or '').strip(),
            })
        elif existing.sale_order_id != self.sale_order_id:
            raise ValidationError(_('La orden de venta no coincide con el expediente.'))
        if self.payment_state != 'refund' and self.gross < 0:
            raise ValidationError(_('El importe de venta no puede ser negativo.'))
        existing._post_event(
            payment_state=self.payment_state, event_time=self.event_time,
            amount=self.amount,
            gross=self.gross, withholding=self.withholding,
            coupon_amount=self.coupon_amount,
            killer_amount=self.killer_amount,
            commission=self.commission,
            killer_commission=self.killer_commission,
            coupon_commission=self.coupon_commission,
            shipping=self.shipping, other=self.other,
            bucket=self.refund_bucket,
            reference=self.reference or '', notes=self.notes or '',
            attachment_data=self.attachment_data,
            attachment_name=self.attachment_name,
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cobranza de %s') % self.sale_order_id.name,
            'res_model': 'mkp.collection.order', 'res_id': existing.id,
            'view_mode': 'form', 'target': 'current',
        }
