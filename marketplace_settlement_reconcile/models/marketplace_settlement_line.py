# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MarketplaceSettlementLine(models.Model):
    _name = "marketplace.settlement.line"
    _description = "Marketplace Settlement Line"
    _order = "id desc"

    settlement_id = fields.Many2one(
        "marketplace.settlement",
        string="Settlement",
        required=True,
        ondelete="cascade",
        index=True,
    )

    company_id = fields.Many2one(related="settlement_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="settlement_id.currency_id", store=True, readonly=True)

    order_ref = fields.Char(string="Order Reference", index=True)

    sale_order_id = fields.Many2one("sale.order", string="Sales Order", index=True)
    invoice_reference = fields.Char(string="Invoice Reference", help="Invoice number/reference coming from the marketplace file.")
    invoice_id = fields.Many2one(
        "account.move",
        string="Invoice",
        domain="[('move_type','=','out_invoice')]",
        index=True,
    )

    amount_gross = fields.Monetary(string="Gross (Invoice Total)", currency_field="currency_id", readonly=True)

    withheld_vat_amount = fields.Monetary(string="Withheld VAT", currency_field="currency_id")
    withheld_vat_account_id = fields.Many2one("account.account", string="Withheld VAT Account")

    shipping_amount = fields.Monetary(string="Shipping Cost", currency_field="currency_id")
    shipping_account_id = fields.Many2one("account.account", string="Shipping Account")

    seller_commission_amount = fields.Monetary(string="Seller Commission", currency_field="currency_id")
    seller_commission_account_id = fields.Many2one("account.account", string="Seller Commission Account")

    amount_fees_total = fields.Monetary(
        string="Total Fees",
        currency_field="currency_id",
        compute="_compute_amount_fees_total",
        store=True,
        readonly=True,
    )

    amount_net = fields.Monetary(
        string="Net to Reconcile",
        currency_field="currency_id",
        compute="_compute_amount_net",
        store=True,
        readonly=True,
        help="Net amount expected to match the bank deposit for this invoice (gross - fees).",
    )

    @api.depends("withheld_vat_amount", "shipping_amount", "seller_commission_amount")
    def _compute_amount_fees_total(self):
        for line in self:
            line.amount_fees_total = (line.withheld_vat_amount or 0.0) + (line.shipping_amount or 0.0) + (line.seller_commission_amount or 0.0)

    @api.depends("amount_gross", "amount_fees_total")
    def _compute_amount_net(self):
        for line in self:
            line.amount_net = (line.amount_gross or 0.0) - (line.amount_fees_total or 0.0)

    @api.onchange("invoice_id")
    def _onchange_invoice_id(self):
        for line in self:
            if not line.invoice_id:
                line.amount_gross = 0.0
                return
            # Invoice total
            line.amount_gross = line.invoice_id.amount_total or 0.0

            # Try to infer Sales Order from invoice lines
            sale_orders = line.invoice_id.invoice_line_ids.mapped("sale_line_ids.order_id")
            line.sale_order_id = sale_orders[:1] if sale_orders else False

            # If invoice ref is empty, use invoice name
            if not line.invoice_reference:
                line.invoice_reference = line.invoice_id.name

    @api.onchange("invoice_reference")
    def _onchange_invoice_reference(self):
        for line in self:
            if not line.invoice_reference or line.invoice_id:
                continue
            inv = self.env["account.move"].search(
                [
                    ("move_type", "=", "out_invoice"),
                    "|",
                    ("name", "=", line.invoice_reference),
                    ("ref", "=", line.invoice_reference),
                ],
                limit=1,
            )
            if inv:
                line.invoice_id = inv

    @api.onchange("order_ref")
    def _onchange_order_ref(self):
        for line in self:
            if not line.order_ref:
                continue
            so = self.env["sale.order"].search([("name", "=", line.order_ref)], limit=1)
            if so:
                line.sale_order_id = so
                # If invoice isn't set yet, try to get latest posted invoice
                if not line.invoice_id:
                    inv = self.env["account.move"].search(
                        [
                            ("move_type", "=", "out_invoice"),
                            ("state", "in", ("posted", "draft")),
                            ("invoice_origin", "ilike", so.name),
                        ],
                        order="id desc",
                        limit=1,
                    )
                    if inv:
                        line.invoice_id = inv
