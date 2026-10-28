# -*- coding: utf-8 -*-
from odoo import fields, models


class MkpPaymentGatewayConfig(models.Model):
    _name = 'mkp.payment.gateway.config'
    _description = 'Configuración de pasarelas de pago'
    _order = 'partner_id'
    _check_company_auto = True

    active = fields.Boolean(default=True)
    partner_id = fields.Many2one(
        'res.partner',
        string='Pasarela de pago',
        required=True,
        ondelete='restrict',
        help='Contacto asociado a la pasarela de pago.',
    )
    commission_expense_account_id = fields.Many2one(
        'account.account',
        string='Cuenta Comisión Pasarela',
        check_company=True,
        help='Cuenta contable para el importe capturado como Comisión Pasarela.',
    )
    fixed_commission_expense_account_id = fields.Many2one(
        'account.account',
        string='Cuenta Comisión Fija',
        check_company=True,
        help='Cuenta contable para el importe capturado como Comisión Fija.',
    )
    commission_vat_account_id = fields.Many2one(
        'account.account',
        string='Cuenta IVA Comisión Pasarela',
        check_company=True,
        help='Cuenta contable para el IVA capturado de la Comisión Pasarela.',
    )
    fixed_commission_vat_account_id = fields.Many2one(
        'account.account',
        string='Cuenta IVA Comisión Fija',
        check_company=True,
        help='Cuenta contable para el IVA capturado de la Comisión Fija.',
    )
    commission_journal_id = fields.Many2one(
        'account.journal',
        string='Diario de comisiones',
        required=True,
        check_company=True,
        domain="[('type', '=', 'general'), ('company_id', '=', company_id)]",
        default=lambda self: self.env['account.journal'].search([
            ('type', '=', 'general'),
            ('company_id', '=', self.env.company.id),
        ], limit=1),
        help='Diario general donde se registrarán las comisiones capturadas.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True,
    )

    _partner_company_unique = models.Constraint(
        'unique(partner_id, company_id)',
        'Ya existe una configuración para esta pasarela en la compañía.',
    )
