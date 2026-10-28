# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Compatibilidad con la versión que admitía una sola pasarela.
    mkp_payment_gateway_config_id = fields.Many2one(
        'mkp.payment.gateway.config',
        string='Pasarela de pago anterior',
        check_company=True,
        copy=False,
    )
    mkp_payment_gateway_partner_id = fields.Many2one(
        'res.partner',
        string='Contacto de la pasarela anterior',
        related='mkp_payment_gateway_config_id.partner_id',
        readonly=True,
    )
    mkp_gateway_payment_line_ids = fields.One2many(
        'mkp.sale.gateway.payment',
        'order_id',
        string='Pagos por pasarela',
        copy=True,
    )
    mkp_gateway_paid_amount = fields.Monetary(
        string='Total asignado a pasarelas',
        currency_field='currency_id',
        compute='_compute_gateway_totals',
        store=True,
    )
    mkp_gateway_unassigned_amount = fields.Monetary(
        string='Importe sin asignar',
        currency_field='currency_id',
        compute='_compute_gateway_totals',
    )
    mkp_gateway_commission_amount = fields.Monetary(
        string='Comisión Pasarela',
        currency_field='currency_id',
        compute='_compute_gateway_totals',
        store=True,
    )
    mkp_gateway_fixed_commission_amount = fields.Monetary(
        string='Comisión Fija',
        currency_field='currency_id',
        compute='_compute_gateway_totals',
        store=True,
    )
    mkp_gateway_commission_vat_amount = fields.Monetary(
        string='IVA Comisión Pasarela',
        currency_field='currency_id',
        compute='_compute_gateway_totals',
        store=True,
    )
    mkp_gateway_fixed_commission_vat_amount = fields.Monetary(
        string='IVA Comisión Fija',
        currency_field='currency_id',
        compute='_compute_gateway_totals',
        store=True,
    )
    mkp_gateway_total_commission_amount = fields.Monetary(
        string='Comisión total estimada',
        currency_field='currency_id',
        compute='_compute_gateway_totals',
        store=True,
    )

    @api.depends(
        'amount_total',
        'mkp_gateway_payment_line_ids.payment_amount',
        'mkp_gateway_payment_line_ids.commission_amount',
        'mkp_gateway_payment_line_ids.fixed_commission_amount',
        'mkp_gateway_payment_line_ids.commission_vat_amount',
        'mkp_gateway_payment_line_ids.fixed_commission_vat_amount',
        'mkp_gateway_payment_line_ids.total_commission_amount',
    )
    def _compute_gateway_totals(self):
        for order in self:
            lines = order.mkp_gateway_payment_line_ids
            paid_amount = sum(lines.mapped('payment_amount'))
            commission_amount = sum(lines.mapped('commission_amount'))
            fixed_amount = sum(lines.mapped('fixed_commission_amount'))
            commission_vat = sum(lines.mapped('commission_vat_amount'))
            fixed_commission_vat = sum(lines.mapped('fixed_commission_vat_amount'))
            order.mkp_gateway_paid_amount = paid_amount
            order.mkp_gateway_unassigned_amount = order.amount_total - paid_amount
            order.mkp_gateway_commission_amount = commission_amount
            order.mkp_gateway_fixed_commission_amount = fixed_amount
            order.mkp_gateway_commission_vat_amount = commission_vat
            order.mkp_gateway_fixed_commission_vat_amount = fixed_commission_vat
            order.mkp_gateway_total_commission_amount = (
                commission_amount + fixed_amount + commission_vat + fixed_commission_vat
            )

    @api.constrains('amount_total', 'mkp_gateway_payment_line_ids')
    def _check_gateway_payment_total(self):
        for order in self:
            order._validate_gateway_payment_total()

    def _validate_gateway_payment_total(self):
        self.ensure_one()
        allocated = sum(self.mkp_gateway_payment_line_ids.mapped('payment_amount'))
        if float_compare(
            allocated,
            self.amount_total,
            precision_rounding=self.currency_id.rounding,
        ) > 0:
            raise ValidationError(_(
                'El total asignado a pasarelas (%(allocated)s) no puede ser mayor '
                'al total de la orden (%(total)s).',
                allocated=allocated,
                total=self.amount_total,
            ))

    def action_confirm(self):
        for order in self:
            order._validate_gateway_payment_total()
        return super().action_confirm()
