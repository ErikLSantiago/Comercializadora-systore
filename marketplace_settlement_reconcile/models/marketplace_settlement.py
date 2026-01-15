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

    is_validated = fields.Boolean(string="Validated", default=False, readonly=True)
    validation_notes = fields.Text(string="Validation Notes", readonly=True)

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
    def action_validate(self):
        """Validate settlement lines before posting.

        Checks:
        - Lines exist.
        - Each line has at least an Order Ref, Sales Order, or Invoice.
        - If an amount is provided for VAT/Shipping/Commission, its account must be set.
        - Sum of 'Net to Reconcile' matches Bank Amount within currency rounding tolerance.
        """
        for settlement in self:
            errors = []
            warnings = []
            if not settlement.line_ids:
                errors.append("No lines to validate.")

            currency = settlement.currency_id or settlement.company_id.currency_id
            rounding = (currency.rounding if currency else 0.01) or 0.01
            tol = rounding * 2

            net_sum = 0.0
            seen_orders = set()

            for i, line in enumerate(settlement.line_ids, start=1):
                if not (line.order_ref or line.sale_order_id or line.invoice_id):
                    errors.append(f"Line {i}: missing Order Ref / Sales Order / Invoice.")
                    continue

                if line.order_ref:
                    if line.order_ref in seen_orders:
                        warnings.append(f"Line {i}: duplicate Order Ref '{line.order_ref}'.")
                    seen_orders.add(line.order_ref)

                if not line.invoice_id:
                    warnings.append(f"Line {i}: no invoice linked.")

                if (line.withheld_vat_amount or 0.0) and not line.withheld_vat_account_id:
                    errors.append(f"Line {i}: Withheld VAT account is required.")
                if (line.shipping_amount or 0.0) and not line.shipping_account_id:
                    errors.append(f"Line {i}: Shipping account is required.")
                if (line.seller_commission_amount or 0.0) and not line.seller_commission_account_id:
                    errors.append(f"Line {i}: Seller commission account is required.")

                net_sum += (line.amount_net or 0.0)

            bank_amt = settlement.amount_bank or 0.0
            diff = bank_amt - net_sum
            if abs(diff) > tol:
                errors.append(
                    f"Bank Amount ({bank_amt:,.2f}) does not match sum of Net to Reconcile ({net_sum:,.2f}). "
                    f"Difference: {diff:,.2f}."
                )

            if errors:
                raise UserError("Validation failed:\n- " + "\n- ".join(errors))

            notes = ""
            if warnings:
                notes = "Warnings:\n- " + "\n- ".join(warnings)

            settlement.write({
                    "is_validated": True,
                    "validation_notes": notes,
                    "state": "imported" if settlement.state == "draft" else settlement.state,
                })

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Validation OK",
                "message": "Settlement validated successfully." + ("\n" + notes if notes else ""),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            }
        }

    def action_post_and_reconcile(self):
        for rec in self:
            rec._ensure_config()
            if rec.state != "imported":
                raise UserError(_("Only imported settlements can be posted."))
            if not rec.is_validated:
                raise UserError(_("Please validate the settlement before posting."))
            if rec.move_id:
                raise UserError(_("This settlement is already posted."))

            # Build settlement accounting entry:
            move_lines = []
            company = rec.company_id
            company_currency = company.currency_id
            currency = rec.currency_id or company_currency

            # Helper to add a line (no amount_currency unless multi-currency is needed)
            def _add_line(name, account, debit=0.0, credit=0.0, partner=False):
                vals = {
                    "name": name or rec.name,
                    "account_id": account.id,
                    "debit": debit,
                    "credit": credit,
                    "partner_id": partner.id if partner else False,
                }
                # Set currency only for multi-currency postings
                if currency and company_currency and currency != company_currency:
                    vals["currency_id"] = currency.id
                    vals["amount_currency"] = (debit - credit)
                return vals

            settlement_date = rec.bank_statement_line_id.date if rec.bank_statement_line_id else fields.Date.context_today(self)

            for line in rec.line_ids.filtered(lambda l: l.invoice_id):
                inv = line.invoice_id

                # Receivable account from invoice
                receivable_ml = inv.line_ids.filtered(lambda ml: ml.account_id.account_type == "asset_receivable")
                if not receivable_ml:
                    raise UserError(_("No receivable line found on invoice %s.") % inv.display_name)
                receivable_account = receivable_ml[0].account_id
                partner = inv.partner_id

                gross = line.amount_gross or inv.amount_total
                net = line.amount_net

                if not gross:
                    continue

                # Debit clearing for net deposit
                if net:
                    move_lines.append(_add_line(_("Net deposit (%s)") % inv.display_name, rec.clearing_account_id, debit=net, partner=partner))

                # Debit expenses (fees)
                if line.withheld_vat_amount and line.withheld_vat_account_id:
                    move_lines.append(_add_line(_("Withheld VAT (%s)") % inv.display_name, line.withheld_vat_account_id, debit=line.withheld_vat_amount, partner=partner))
                if line.shipping_amount and line.shipping_account_id:
                    move_lines.append(_add_line(_("Shipping cost (%s)") % inv.display_name, line.shipping_account_id, debit=line.shipping_amount, partner=partner))
                if line.seller_commission_amount and line.seller_commission_account_id:
                    move_lines.append(_add_line(_("Seller commission (%s)") % inv.display_name, line.seller_commission_account_id, debit=line.seller_commission_amount, partner=partner))

                # Credit receivable for full invoice amount (marks invoice as paid when reconciled)
                move_lines.append(_add_line(_("Customer receivable (%s)") % inv.display_name, receivable_account, credit=gross, partner=partner))

            if not move_lines:
                raise UserError(_("Nothing to post. Please add at least one line with an invoice."))

            move_vals = {
                "move_type": "entry",
                "journal_id": rec.journal_id.id,
                "date": settlement_date,
                "ref": rec.name,
                "company_id": rec.company_id.id,
                "line_ids": [(0, 0, vals) for vals in move_lines],
            }
            move = self.env["account.move"].create(move_vals)

            # Ensure balanced before posting (avoid cryptic errors)
            debit = sum(ml["debit"] for ml in move_lines)
            credit = sum(ml["credit"] for ml in move_lines)
            if not company_currency.is_zero(debit - credit):
                raise UserError(_("The settlement entry is not balanced. Debit=%s Credit=%s Difference=%s") % (debit, credit, debit - credit))

            move.action_post()
            rec.move_id = move.id

            # Reconcile each invoice receivable with the corresponding credit line from the settlement move
            for line in rec.line_ids.filtered(lambda l: l.invoice_id):
                inv = line.invoice_id
                gross = line.amount_gross or inv.amount_total
                if not gross:
                    continue

                inv_recv_lines = inv.line_ids.filtered(lambda ml: ml.account_id.account_type == "asset_receivable" and not ml.reconciled)
                if not inv_recv_lines:
                    continue
                recv_account = inv_recv_lines[0].account_id

                settlement_recv_lines = move.line_ids.filtered(
                    lambda ml: ml.account_id.id == recv_account.id
                    and ml.partner_id.id == inv.partner_id.id
                    and ml.credit
                    and not ml.reconciled
                )

                # pick the closest credit line by amount
                target = settlement_recv_lines.filtered(lambda ml: company_currency.is_zero(ml.credit - gross))
                target = target[:1] or settlement_recv_lines[:1]
                if target and inv_recv_lines:
                    (inv_recv_lines | target).reconcile()

            # Reconcile clearing with the bank statement line by creating a bank move and linking it
            if rec.bank_statement_line_id:
                bsl = rec.bank_statement_line_id
                bank_journal = bsl.journal_id
                bank_account = bank_journal.default_account_id
                if not bank_account:
                    raise UserError(_("Please configure a default account on the bank journal %s.") % bank_journal.display_name)

                amount = rec.amount_bank
                if company_currency.is_zero(amount):
                    amount = sum(rec.line_ids.mapped("amount_net"))

                bank_move_lines = []
                partner = bsl.partner_id
                if amount > 0:
                    bank_move_lines.append(_add_line(_("Bank deposit (%s)") % rec.name, bank_account, debit=amount, partner=partner))
                    bank_move_lines.append(_add_line(_("Marketplace clearing (%s)") % rec.name, rec.clearing_account_id, credit=amount, partner=partner))
                else:
                    amt = abs(amount)
                    bank_move_lines.append(_add_line(_("Bank payment (%s)") % rec.name, bank_account, credit=amt, partner=partner))
                    bank_move_lines.append(_add_line(_("Marketplace clearing (%s)") % rec.name, rec.clearing_account_id, debit=amt, partner=partner))

                bank_move = self.env["account.move"].create({
                    "move_type": "entry",
                    "journal_id": bank_journal.id,
                    "date": bsl.date,
                    "ref": rec.name,
                    "company_id": rec.company_id.id,
                    "line_ids": [(0, 0, vals) for vals in bank_move_lines],
                })
                bank_move.action_post()

                # Link statement line to this move (so it shows as matched) - ignore if field is computed
                write_vals = {}
                if "move_id" in bsl._fields:
                    write_vals["move_id"] = bank_move.id
                if "is_reconciled" in bsl._fields:
                    write_vals["is_reconciled"] = True
                if "checked" in bsl._fields:
                    write_vals["checked"] = True
                if write_vals:
                    bsl.write(write_vals)

                # Reconcile clearing between settlement entry and bank entry
                if not rec.clearing_account_id.reconcile:
                    raise UserError(_("Clearing account %s must allow reconciliation.") % rec.clearing_account_id.display_name)

                clearing_lines = (move.line_ids | bank_move.line_ids).filtered(
                    lambda ml: ml.account_id.id == rec.clearing_account_id.id and not ml.reconciled
                )
                if clearing_lines:
                    clearing_lines.reconcile()

            rec.state = "posted"

    def _compute_amount_gross(self):
        for rec in self:
            inv = rec.invoice_id
            if inv:
                # amount_total is always in invoice currency; use it to match operational expectations
                rec.amount_gross = inv.amount_total or 0.0
            else:
                rec.amount_gross = 0.0

    @api.onchange("order_ref")
    def _onchange_order_ref_link_documents(self):
        for rec in self:
            if not rec.order_ref:
                continue
            # Link Sales Order by name
            so = self.env["sale.order"].search([("name", "=", rec.order_ref)], limit=1)
            if so:
                rec.sale_order_id = so
                # Prefer posted customer invoice linked to the SO
                inv = so.invoice_ids.filtered(lambda m: m.move_type in ("out_invoice", "out_refund") and m.state == "posted")
                rec.invoice_id = inv[:1] if inv else so.invoice_ids[:1]
            else:
                # fallback: try to find invoice by invoice_origin
                inv = self.env["account.move"].search([
                    ("move_type", "in", ("out_invoice", "out_refund")),
                    ("invoice_origin", "=", rec.order_ref),
                ], limit=1, order="id desc")
                rec.invoice_id = inv

    amount_gross = fields.Monetary(string="Gross (Invoice Total)", compute="_compute_amount_gross", store=True, readonly=True)
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
