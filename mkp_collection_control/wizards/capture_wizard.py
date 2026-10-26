from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class MkpCollectionCaptureWizard(models.TransientModel):
    _name = 'mkp.collection.capture.wizard'
    _description = 'Captura manual de eventos de cobranza'

    sale_order_id = fields.Many2one('sale.order', string='Orden de venta', required=True)
    order_id = fields.Many2one('mkp.collection.order', string='Expediente de cobranza', readonly=True)
    marketplace = fields.Char('Marketplace')
    marketplace_reference = fields.Char('Número de orden MKP')
    event_type = fields.Selection([
        ('opening', 'Desglose inicial'), ('hold', 'Reconocer importe retenido'),
        ('unlock', 'Regresar fondos retenidos a por cobrar'),
        ('release', 'Liberar fondos retenidos'),
        ('release_direct', 'Reconocer importe liberado directamente'),
        ('payment', 'Pago informado por marketplace'),
        ('coupon', 'Cupón confirmado'), ('killer', 'Killer confirmado'),
        ('commission', 'Ajuste de comisión'), ('tax', 'Ajuste de impuestos / retenciones'),
        ('shipping', 'Ajuste de envío'), ('other', 'Otras comisiones (incluye guía)'),
        ('refund', 'Devolución financiera básica'),
    ], string='¿Qué sucedió?', required=True, default='opening')
    event_time = fields.Datetime('Fecha y hora del evento', required=True,
                                 default=fields.Datetime.now)
    initial_gross = fields.Monetary('Venta inicial', currency_field='currency_id')
    initial_withholding = fields.Monetary('Retenciones / impuestos', currency_field='currency_id')
    initial_commission = fields.Monetary('Comisión inicial', currency_field='currency_id')
    initial_shipping = fields.Monetary('Envío inicial', currency_field='currency_id')
    initial_other = fields.Monetary('Otras comisiones iniciales', currency_field='currency_id')
    amount = fields.Monetary('Importe del evento', currency_field='currency_id')
    extra_commission = fields.Monetary('Comisión adicional del cupón / killer',
                                       currency_field='currency_id')
    refund_bucket = fields.Selection([
        ('pending', 'Monto por cobrar'), ('held', 'Retenido'),
        ('released', 'Liberado'), ('paid', 'Pago reportado')],
        string='¿De qué saldo se descuenta?', default='pending')
    currency_id = fields.Many2one(related='sale_order_id.currency_id', readonly=True)
    reference = fields.Char('Referencia del reporte / marketplace')
    notes = fields.Text('Motivo / observaciones')
    attachment_data = fields.Binary('Evidencia del movimiento', attachment=False)
    attachment_name = fields.Char('Nombre del archivo')

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
                if not existing.initialized:
                    vals['event_type'] = 'opening'
        if sale_id:
            sale = self.env['sale.order'].browse(sale_id)
            if sale.exists():
                vals['initial_gross'] = sale.amount_total
                if not order_id:
                    vals['marketplace_reference'] = self._get_sale_marketplace_ref(sale)
        return vals

    @api.model
    def _get_sale_marketplace_ref(self, sale):
        for field_name in ('x_studio_nmero_de_orden_mkp', 'x_studio_numero_de_orden_mkp'):
            if field_name in sale._fields and sale[field_name]:
                return str(sale[field_name])
        return sale.client_order_ref or sale.origin or ''

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        if self.sale_order_id:
            existing = self.env['mkp.collection.order'].search([
                ('sale_order_id', '=', self.sale_order_id.id)], limit=1)
            self.order_id = existing
            self.initial_gross = self.sale_order_id.amount_total
            if existing:
                self.marketplace = existing.marketplace
                self.marketplace_reference = existing.marketplace_reference
                if not existing.initialized:
                    self.event_type = 'opening'
                elif self.event_type == 'opening':
                    self.event_type = 'hold'
            else:
                self.event_type = 'opening'
                self.marketplace = False
                self.marketplace_reference = self._get_sale_marketplace_ref(self.sale_order_id)

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group('mkp_collection_control.group_mkp_collection_operator'):
            raise AccessError(_('Debe pertenecer al grupo Operador de Cobranza MKP.'))
        if not self.sale_order_id.exists():
            raise ValidationError(_('Seleccione una orden válida.'))
        # Read with caller's rights: never use sudo to bypass sale.order security.
        self.sale_order_id.read(['name', 'amount_total', 'company_id'])
        existing = self.env['mkp.collection.order'].search([
            ('sale_order_id', '=', self.sale_order_id.id)], limit=1)
        if not existing:
            if self.event_type != 'opening':
                raise ValidationError(_('Primero registre el desglose inicial.'))
            if not self.marketplace or not self.marketplace.strip():
                raise ValidationError(_('Indique el marketplace del pedido.'))
            existing = self.env['mkp.collection.order'].sudo().create({
                'sale_order_id': self.sale_order_id.id,
                'marketplace': self.marketplace.strip(),
                'marketplace_reference': (self.marketplace_reference or '').strip(),
            })
        elif existing.sale_order_id != self.sale_order_id:
            raise ValidationError(_('La orden de venta no coincide con el expediente.'))
        if self.event_type == 'opening' and self.initial_gross < 0:
            raise ValidationError(_('El importe original no puede ser negativo.'))
        existing._post_event(
            kind=self.event_type, event_time=self.event_time,
            amount=self.amount, extra_commission=self.extra_commission,
            gross=self.initial_gross, withholding=self.initial_withholding,
            commission=self.initial_commission, shipping=self.initial_shipping,
            other=self.initial_other, bucket=self.refund_bucket,
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
