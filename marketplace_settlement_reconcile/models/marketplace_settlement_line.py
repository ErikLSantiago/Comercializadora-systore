# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class MarketplaceSettlementLine(models.Model):
    _name = 'marketplace.settlement.line'
    _description = 'Marketplace Settlement Line'
    _order = 'id desc'

    settlement_id = fields.Many2one(
        'marketplace.settlement',
        string='Settlement',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(related='settlement_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(related='settlement_id.currency_id', store=True, readonly=True)

    order_ref = fields.Char(string='Order Reference')
    sale_order_id = fields.Many2one('sale.order', string='Sales Order', ondelete='set null')
    invoice_reference = fields.Char(string='Invoice Reference')
    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice',
        domain="[('move_type','in',('out_invoice','out_refund'))]",
        ondelete='set null',
    )

    amount_gross = fields.Monetary(string='Gross (Invoice Total)', currency_field='currency_id', compute='_compute_amount_gross', store=True, readonly=True)

    withheld_vat_amount = fields.Monetary(string='Withheld VAT', currency_field='currency_id')
    withheld_vat_account_id = fields.Many2one('account.account', string='Withheld VAT Account')

    shipping_amount = fields.Monetary(string='Shipping Cost', currency_field='currency_id')
    shipping_account_id = fields.Many2one('account.account', string='Shipping Account')

    seller_commission_amount = fields.Monetary(string='Seller Commission', currency_field='currency_id')
    seller_commission_account_id = fields.Many2one('account.account', string='Seller Commission Account')

    amount_net = fields.Monetary(string='Net to Reconcile', currency_field='currency_id', compute='_compute_amount_net', store=True, readonly=True)

    @api.depends('invoice_id.amount_total')
    def _compute_amount_gross(self):
        for line in self:
            line.amount_gross = line.invoice_id.amount_total or 0.0

    @api.depends('amount_gross', 'withheld_vat_amount', 'shipping_amount', 'seller_commission_amount')
    def _compute_amount_net(self):
        for line in self:
            gross = line.amount_gross or 0.0
            line.amount_net = gross - (line.withheld_vat_amount or 0.0) - (line.shipping_amount or 0.0) - (line.seller_commission_amount or 0.0)

    @api.onchange('order_ref')
    def _onchange_order_ref(self):
        for line in self:
            if not line.order_ref:
                continue
            so = self.env['sale.order'].search([('name', '=', line.order_ref)], limit=1)
            if so:
                line.sale_order_id = so.id
                # Try pick invoice from SO if present
                inv = so.invoice_ids.filtered(lambda m: m.move_type in ('out_invoice', 'out_refund') and m.state != 'cancel')[:1]
                if inv:
                    line.invoice_id = inv.id
                    line.invoice_reference = inv.name

    @api.onchange('invoice_reference')
    def _onchange_invoice_reference(self):
        for line in self:
            if not line.invoice_reference:
                continue
            inv = self.env['account.move'].search([
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                '|', ('name', '=', line.invoice_reference), ('ref', '=', line.invoice_reference),
            ], limit=1)
            if inv:
                line.invoice_id = inv.id
                if not line.invoice_reference:
                    line.invoice_reference = inv.name
