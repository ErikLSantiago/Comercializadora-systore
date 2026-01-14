# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class MarketplaceSettlement(models.Model):
    _name = "marketplace.settlement"
    _description = "Marketplace Settlement"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(default=lambda self: _("New Settlement"), required=True, tracking=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("imported", "Imported"),
        ("posted", "Posted"),
    ], default="draft", tracking=True)

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id, required=True)
    bank_statement_line_id = fields.Many2one("account.bank.statement.line", string="Bank Statement Line", ondelete="set null")
    amount_bank = fields.Monetary(string="Bank Amount (Net Deposit)", tracking=True)

    journal_id = fields.Many2one(
        "account.journal",
        string="Settlement Journal",
        domain=[("type", "=", "general")],
        default=lambda self: self.env.company.mkp_settlement_journal_id,
        required=False,
    )
    clearing_account_id = fields.Many2one(
        "account.account",
        string="Clearing Account",
        default=lambda self: self.env.company.mkp_clearing_account_id,
        required=False,
    )
    move_id = fields.Many2one("account.move", string="Posted Entry", readonly=True)

    line_ids = fields.One2many("marketplace.settlement.line", "settlement_id", string="Lines")
    amount_gross = fields.Monetary(compute="_compute_totals", store=True)
    amount_fees = fields.Monetary(compute="_compute_totals", store=True)
    amount_net = fields.Monetary(compute="_compute_totals", store=True)
    amount_diff = fields.Monetary(compute="_compute_totals", store=True, string="Difference vs Bank")

    @api.depends("line_ids.amount_gross", "line_ids.amount_fees_total", "line_ids.amount_net", "amount_bank")
    def _compute_totals(self):
        for rec in self:
            gross = sum(rec.line_ids.mapped("amount_gross"))
            fees = sum(rec.line_ids.mapped("amount_fees_total"))
            net = sum(rec.line_ids.mapped("amount_net"))
            rec.amount_gross = gross
            rec.amount_fees = fees
            rec.amount_net = net
            rec.amount_diff = (rec.amount_bank or 0.0) - net

    def action_open_form(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Marketplace Settlement"),
            "res_model": "marketplace.settlement",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_set_draft(self):
        for rec in self:
            if rec.move_id:
                raise UserError(_("Cannot revert to Draft once posted."))
            rec.state = "draft"

    def action_mark_imported(self):
        self.write({"state": "imported"})

    def _ensure_config(self):
        for rec in self:
            if not rec.journal_id:
                raise UserError(_("Please configure a Settlement Journal (Accounting Settings)."))
            if not rec.clearing_account_id:
                raise UserError(_("Please configure a Clearing Account (Accounting Settings)."))

    def action_post_and_reconcile(self):
        for rec in self:
            rec._ensure_config()
            if rec.move_id:
                raise UserError(_("This settlement is already posted."))

            if not rec.line_ids:
                raise UserError(_("No lines to post. Import a CSV first."))

            # Build a single balanced journal entry:
            # For each invoice: credit receivable by gross; debit clearing by net; debit expense accounts by fees.
            lines_vals = []
            company = rec.company_id
            currency = rec.currency_id

            for line in rec.line_ids:
                inv = line.invoice_id
                if not inv or inv.state != "posted" or inv.move_type not in ("out_invoice", "out_refund"):
                    raise UserError(_("Each settlement line must have a posted customer invoice. Check line: %s") % (line.order_ref or line.id))

                # Determine invoice receivable account
                receivable_lines = inv.line_ids.filtered(lambda l: l.account_id.account_type == "asset_receivable" and not l.reconciled)
                if not receivable_lines:
                    raise UserError(_("Invoice %s has no open receivable line to reconcile.") % inv.name)
                receivable_account = receivable_lines[0].account_id

                # Credit receivable by gross
                lines_vals.append((0, 0, {
                    "name": _("Settlement - %s") % (inv.name),
                    "account_id": receivable_account.id,
                    "partner_id": inv.partner_id.id,
                    "credit": line.amount_gross if line.amount_gross > 0 else 0.0,
                    "debit": (-line.amount_gross) if line.amount_gross < 0 else 0.0,
                    "currency_id": currency.id if currency != company.currency_id else False,
                    "amount_currency": 0.0,
                }))

                # Debit clearing by net
                lines_vals.append((0, 0, {
                    "name": _("Net deposit - %s") % (inv.name),
                    "account_id": rec.clearing_account_id.id,
                    "partner_id": False,
                    "debit": line.amount_net if line.amount_net > 0 else 0.0,
                    "credit": (-line.amount_net) if line.amount_net < 0 else 0.0,
                }))

                # Debit fees
                fee_components = [
                    ("Withheld VAT", line.withheld_vat_amount, line.withheld_vat_account_id),
                    ("Shipping", line.shipping_amount, line.shipping_account_id),
                    ("Seller Commission", line.seller_commission_amount, line.seller_commission_account_id),
                ]
                for label, amt, acc in fee_components:
                    if not amt:
                        continue
                    if not acc:
                        raise UserError(_("Missing account for %s on invoice %s.") % (label, inv.name))
                    lines_vals.append((0, 0, {
                        "name": _("%s - %s") % (label, inv.name),
                        "account_id": acc.id,
                        "partner_id": False,
                        "debit": amt if amt > 0 else 0.0,
                        "credit": (-amt) if amt < 0 else 0.0,
                    }))

            move = self.env["account.move"].create({
                "move_type": "entry",
                "date": rec.bank_statement_line_id.date if rec.bank_statement_line_id else fields.Date.context_today(self),
                "ref": rec.name,
                "journal_id": rec.journal_id.id,
                "company_id": rec.company_id.id,
                "line_ids": lines_vals,
            })
            move.action_post()
            rec.move_id = move.id
            rec.state = "posted"

            # Reconcile receivable lines per invoice
            for line in rec.line_ids:
                inv = line.invoice_id
                inv_recv = inv.line_ids.filtered(lambda l: l.account_id.account_type == "asset_receivable" and not l.reconciled)
                if not inv_recv:
                    continue
                # Find matching settlement receivable line in the move (same partner/account and opposite sign)
                st_recv = move.line_ids.filtered(lambda l:
                    l.account_id == inv_recv[0].account_id and l.partner_id == inv.partner_id and not l.reconciled
                )
                # reconcile all matching for safety
                (inv_recv + st_recv).reconcile()

            # NOTE: Bank reconciliation (statement line) is left to the standard widget:
            # user matches the bank statement line with the clearing account lines from this move.
            return rec.action_open_form()

class MarketplaceSettlementLine(models.Model):
    _name = "marketplace.settlement.line"
    _description = "Marketplace Settlement Line"
    _order = "id asc"

    settlement_id = fields.Many2one("marketplace.settlement", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="settlement_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="settlement_id.currency_id", store=True, readonly=True)

    order_ref = fields.Char(string="Order Reference", required=True)
    sale_order_id = fields.Many2one("sale.order", string="Sales Order", ondelete="set null")
    invoice_id = fields.Many2one("account.move", string="Invoice", ondelete="set null")

    amount_gross = fields.Monetary(string="Gross (Invoice Total)", readonly=True)
    withheld_vat_amount = fields.Monetary(string="Withheld VAT")
    withheld_vat_account_id = fields.Many2one("account.account", string="Withheld VAT Account")

    shipping_amount = fields.Monetary(string="Shipping Cost")
    shipping_account_id = fields.Many2one("account.account", string="Shipping Account")

    seller_commission_amount = fields.Monetary(string="Seller Commission")
    seller_commission_account_id = fields.Many2one("account.account", string="Seller Commission Account")

    amount_fees_total = fields.Monetary(compute="_compute_amounts", store=True, string="Total Fees")
    amount_net = fields.Monetary(compute="_compute_amounts", store=True, string="Net to Reconcile")

    @api.depends("amount_gross", "withheld_vat_amount", "shipping_amount", "seller_commission_amount")
    def _compute_amounts(self):
        for rec in self:
            fees = (rec.withheld_vat_amount or 0.0) + (rec.shipping_amount or 0.0) + (rec.seller_commission_amount or 0.0)
            rec.amount_fees_total = fees
            rec.amount_net = (rec.amount_gross or 0.0) - fees

    def action_open_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No invoice linked."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.invoice_id.id,
            "view_mode": "form",
            "target": "current",
        }
