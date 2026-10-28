# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MkpSaleGatewayPayment(models.Model):
    _name = 'mkp.sale.gateway.payment'
    _description = 'Pago de orden de venta por pasarela'
    _order = 'sequence, id'
    _check_company_auto = True

    sequence = fields.Integer(default=10)
    order_id = fields.Many2one(
        'sale.order', string='Orden de venta', required=True,
        ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(
        related='order_id.company_id', store=True, index=True, precompute=True,
    )
    currency_id = fields.Many2one(
        related='order_id.currency_id', store=True, precompute=True,
    )
    gateway_config_id = fields.Many2one(
        'mkp.payment.gateway.config', string='Pasarela', required=True,
        check_company=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
    )
    gateway_partner_id = fields.Many2one(
        related='gateway_config_id.partner_id', string='Contacto',
    )
    payment_amount = fields.Monetary(
        string='Importe pagado', currency_field='currency_id', required=True,
    )
    commission_amount = fields.Monetary(
        string='Comisión Pasarela', currency_field='currency_id', default=0.0,
        help='Importe capturado manualmente; el módulo no aplica porcentajes.',
    )
    fixed_commission_amount = fields.Monetary(
        string='Comisión Fija', currency_field='currency_id', default=0.0,
    )
    commission_vat_amount = fields.Monetary(
        string='IVA Comisión Pasarela', currency_field='currency_id', default=0.0,
    )
    fixed_commission_vat_amount = fields.Monetary(
        string='IVA Comisión Fija', currency_field='currency_id', default=0.0,
    )
    total_commission_amount = fields.Monetary(
        string='Comisión total', currency_field='currency_id',
        compute='_compute_total_commission', store=True,
    )

    _payment_amount_positive = models.Constraint(
        'CHECK(payment_amount > 0)',
        'El importe pagado debe ser mayor que cero.',
    )
    _commission_amount_nonnegative = models.Constraint(
        'CHECK(commission_amount >= 0)',
        'La Comisión Pasarela no puede ser negativa.',
    )
    _fixed_commission_amount_nonnegative = models.Constraint(
        'CHECK(fixed_commission_amount >= 0)',
        'La Comisión Fija no puede ser negativa.',
    )
    _commission_vat_amount_nonnegative = models.Constraint(
        'CHECK(commission_vat_amount >= 0)',
        'El IVA Comisión Pasarela no puede ser negativo.',
    )
    _fixed_commission_vat_amount_nonnegative = models.Constraint(
        'CHECK(fixed_commission_vat_amount >= 0)',
        'El IVA Comisión Fija no puede ser negativo.',
    )

    @api.depends(
        'commission_amount', 'fixed_commission_amount',
        'commission_vat_amount', 'fixed_commission_vat_amount',
    )
    def _compute_total_commission(self):
        for line in self:
            line.total_commission_amount = (
                line.commission_amount
                + line.fixed_commission_amount
                + line.commission_vat_amount
                + line.fixed_commission_vat_amount
            )

    @api.constrains('payment_amount', 'gateway_config_id', 'order_id')
    def _check_payment_line(self):
        for line in self:
            if line.gateway_config_id.company_id != line.company_id:
                raise ValidationError(_(
                    'La pasarela debe pertenecer a la misma compañía de la orden.'
                ))
            line.order_id._validate_gateway_payment_total()
