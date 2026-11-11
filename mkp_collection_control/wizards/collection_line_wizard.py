from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from ..models.collection_line_history import (
    MONETARY_REVISION_FIELDS, NON_MONETARY_REVISION_FIELDS, REVISION_FIELDS,
)
from ..models.ledger import collection_line_totals


class MkpCollectionLineWizard(models.TransientModel):
    _name = 'mkp.collection.line.wizard'
    _description = 'Modificación de línea de cobranza'

    history_id = fields.Many2one(
        'mkp.collection.line.history', string='Línea vigente', required=True, readonly=True
    )
    target_sale_line_id = fields.Many2one(
        'sale.order.line', string='Línea de producto', required=True
    )
    wizard_order_id = fields.Many2one(
        'sale.order', string='Orden de venta', required=True, readonly=True
    )
    sale_order_id = fields.Many2one(
        related='history_id.sale_order_id', string='Orden de venta', readonly=True
    )
    sku = fields.Char(related='history_id.sku', string='SKU', readonly=True)
    product_name = fields.Char(
        related='history_id.product_name', string='Producto', readonly=True
    )
    quantity = fields.Float(
        related='history_id.quantity', string='Cantidad', readonly=True
    )
    uom_name = fields.Char(related='history_id.uom_name', string='Unidad', readonly=True)
    price_unit = fields.Monetary(
        related='history_id.price_unit', string='Precio unitario', readonly=True
    )
    amount = fields.Monetary(
        related='history_id.amount', string='Importe', readonly=True
    )
    currency_id = fields.Many2one(
        related='history_id.currency_id', readonly=True
    )

    coupon_amount = fields.Monetary('Cupón', currency_field='currency_id')
    killer_amount = fields.Monetary('Killer', currency_field='currency_id')
    killer_commission = fields.Monetary('Comisión killer', currency_field='currency_id')
    commission = fields.Monetary('Comisiones', currency_field='currency_id')
    taxes = fields.Monetary('Impuestos', currency_field='currency_id')
    shipping = fields.Monetary('Envío', currency_field='currency_id')
    other_commission = fields.Monetary('Otras comisiones', currency_field='currency_id')
    calculation_type = fields.Selection([
        ('precalculation', 'Precalculo'),
        ('marketplace', 'Marketplace'),
    ], string='Tipo de cálculo', required=True, default='precalculation')
    payment_status = fields.Selection([
        ('held', 'Retenido'),
        ('pending', 'Pendiente'),
        ('paid', 'Pagado'),
        ('cancelled', 'Cancelado'),
        ('refund', 'Reembolso'),
    ], string='Estado de pago', required=True, default='pending')
    payment_reference = fields.Char('Referencia de pago')
    return_status = fields.Selection([
        ('created', 'Devolución creada'),
        ('new', 'Nuevo'),
        ('open_box', 'Open box'),
        ('claim_payment', 'Pago por reclamo'),
        ('subtraction', 'Sustracción'),
        ('refund', 'Reembolso'),
        ('sale', 'Venta'),
    ], string='Estado de devolución', required=True, default='sale')
    return_request_date = fields.Date('Fecha de solicitud')
    return_reference = fields.Char('Referencia')
    return_quantity = fields.Float(
        'Cantidad a devolver', digits='Product Unit of Measure', default=0
    )
    subtotal = fields.Monetary(
        'Sub total', currency_field='currency_id', compute='_compute_totals'
    )
    adjusted_total = fields.Monetary(
        'Total ajustado', currency_field='currency_id', compute='_compute_totals'
    )
    amount_to_collect = fields.Monetary(
        'Por cobrar', currency_field='currency_id', compute='_compute_totals'
    )
    comment = fields.Text('Comentario')

    @api.model
    def default_get(self, field_names):
        values = super().default_get(field_names)
        history_id = values.get('history_id') or self.env.context.get('default_history_id')
        history = self.env['mkp.collection.line.history'].browse(history_id).exists()
        if history:
            values['wizard_order_id'] = history.sale_order_id.id
            values['target_sale_line_id'] = history.sale_line_id.id
            for field_name in REVISION_FIELDS:
                values[field_name] = history[field_name]
        return values

    @api.onchange('target_sale_line_id')
    def _onchange_target_sale_line_id(self):
        if not self.target_sale_line_id:
            return
        if self.wizard_order_id and self.target_sale_line_id.order_id != self.wizard_order_id:
            self.target_sale_line_id = False
            return {
                'warning': {
                    'title': _('Línea no válida'),
                    'message': _('Seleccione una línea de la misma orden de venta.'),
                }
            }
        history = self.env['mkp.collection.line.history'].search([
            ('sale_order_id', '=', self.wizard_order_id.id),
            ('sale_line_id', '=', self.target_sale_line_id.id),
            ('is_active_revision', '=', True),
        ], limit=1)
        if not history:
            return {
                'warning': {
                    'title': _('Línea no disponible'),
                    'message': _(
                        'La línea seleccionada todavía no tiene una versión activa de cobranza.'
                    ),
                }
            }
        self.history_id = history
        for field_name in REVISION_FIELDS:
            self[field_name] = history[field_name]

    @api.depends('amount', *MONETARY_REVISION_FIELDS)
    def _compute_totals(self):
        for wizard in self:
            subtotal, final_total = collection_line_totals(
                amount=wizard.amount,
                coupon_amount=wizard.coupon_amount,
                killer_amount=wizard.killer_amount,
                killer_commission=wizard.killer_commission,
                commission=wizard.commission,
                taxes=wizard.taxes,
                shipping=wizard.shipping,
                other_commission=wizard.other_commission,
            )
            wizard.subtotal = subtotal
            wizard.adjusted_total = final_total
            wizard.amount_to_collect = final_total

    @api.onchange('return_status')
    def _onchange_return_status(self):
        if self.return_status == 'sale':
            self.return_quantity = 0

    def action_confirm(self):
        self.ensure_one()
        history = self.env['mkp.collection.line.history'].search([
            ('sale_order_id', '=', self.wizard_order_id.id),
            ('sale_line_id', '=', self.target_sale_line_id.id),
            ('is_active_revision', '=', True),
        ], limit=1)
        if not history:
            raise ValidationError(_('La línea histórica ya no está disponible.'))
        changes = {}
        for field_name in MONETARY_REVISION_FIELDS:
            if history.currency_id.compare_amounts(
                    history[field_name], self[field_name]):
                changes[field_name] = self[field_name]
        for field_name in NON_MONETARY_REVISION_FIELDS:
            if history[field_name] != self[field_name]:
                changes[field_name] = self[field_name]
        if history.return_quantity != self.return_quantity:
            changes['return_quantity'] = self.return_quantity
        if not changes:
            raise ValidationError(_('No hay cambios para guardar.'))
        history._create_revision(changes, comment=self.comment or '')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Historial de movimientos de cobranza'),
            'res_model': 'mkp.collection.line.history',
            'view_mode': 'list,form',
            'domain': [('sale_order_id', '=', history.sale_order_id.id)],
            'target': 'current',
        }
