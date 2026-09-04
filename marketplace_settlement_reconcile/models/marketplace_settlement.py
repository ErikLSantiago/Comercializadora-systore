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

    def action_download_csv_template(self):
        """Return an action to download a sample CSV template with the expected headers."""
        return {
            "type": "ir.actions.act_url",
            "url": "/marketplace_settlement_reconcile/static/template/marketplace_settlement_template.csv",
            "target": "self",
        }

    def _ensure_config(self):
        for rec in self:
            if not rec.journal_id:
                raise UserError(_("Please configure a Settlement Journal (Accounting Settings)."))
            if not rec.clearing_account_id:
                raise UserError(_("Please configure a Clearing Account (Accounting Settings)."))

    def _create_bank_move_for_statement_line(self, st_line, clearing_account, ref=None):
        """Create a bank journal entry for a bank statement line, using the clearing account as counterpart.

        This is what makes the bank statement line appear as reconciled in the bank reconciliation widget.
        """
        self.ensure_one()

        bank_journal = st_line.journal_id
        if not bank_journal:
            raise UserError(_("Bank Statement Line has no journal."))

        bank_account = bank_journal.default_account_id
        if not bank_account:
            raise UserError(_("Please configure a Default Account on the bank journal '%s'.") % bank_journal.display_name)

        amount = st_line.amount or 0.0
        if amount == 0.0:
            raise UserError(_("Bank statement amount is 0. Cannot create bank move."))

        debit_bank = amount if amount > 0.0 else 0.0
        credit_bank = -amount if amount < 0.0 else 0.0
        debit_clear = credit_bank
        credit_clear = debit_bank

        move_vals = {
            "move_type": "entry",
            "journal_id": bank_journal.id,
            "date": st_line.date or fields.Date.context_today(self),
            "ref": ref or self.name,
            "line_ids": [
                (0, 0, {
                    "name": ref or self.name,
                    "account_id": bank_account.id,
                    "debit": debit_bank,
                    "credit": credit_bank,
                    "partner_id": st_line.partner_id.id if st_line.partner_id else False,
                }),
                (0, 0, {
                    "name": ref or self.name,
                    "account_id": clearing_account.id,
                    "debit": debit_clear,
                    "credit": credit_clear,
                    "partner_id": st_line.partner_id.id if st_line.partner_id else False,
                }),
            ],
        }
        return self.env["account.move"].sudo().create(move_vals)
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
            if rec.move_id:
                raise UserError(_("This settlement is already posted."))

            if not rec.line_ids:
                raise UserError(_("No lines to post. Import a CSV first."))

            # Build a single balanced journal entry:
            # For each invoice: credit receivable by gross; debit clearing by net; debit expense accounts by fees.
            lines_vals = []
            company = rec.company_id
            company_currency = company.currency_id
            currency = rec.currency_id or company_currency

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

            # --- Safety: ensure move is balanced (handle rounding differences) ---
            total_debit = sum(v[2].get("debit", 0.0) for v in lines_vals)
            total_credit = sum(v[2].get("credit", 0.0) for v in lines_vals)
            diff = currency.round(total_debit - total_credit)
            if diff:
                # If debits > credits, add a credit line (and viceversa) on the clearing account.
                lines_vals.append((0, 0, {
                    "name": _("Rounding adjustment"),
                    "account_id": rec.clearing_account_id.id,
                    "partner_id": False,
                    "debit": (-diff) if diff < 0 else 0.0,
                    "credit": diff if diff > 0 else 0.0,
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

            # --- Bank statement line reconciliation (mark as "Conciliado") ---
            # Bank reconciliation widget expects a posted journal entry linked to the
            # bank statement line (move_id) with a bank account line + counterpart.
            # We therefore create (or reuse) a bank move in the bank journal:
            #   Dr/Cr Bank account
            #   Cr/Dr Clearing account
            # and then reconcile the clearing account against the settlement move.
            st_line = rec.bank_statement_line_id
            if st_line:
                bank_move = st_line.move_id
                if not bank_move:
                    bank_journal = st_line.journal_id
                    bank_account = bank_journal.default_account_id
                    if not bank_account:
                        raise UserError(
                            _("Please configure the Default Account on the bank journal: %s")
                            % bank_journal.display_name
                        )

                    amt = st_line.amount or 0.0
                    # Positive amount = bank deposit
                    bank_debit = amt if amt > 0 else 0.0
                    bank_credit = -amt if amt < 0 else 0.0
                    cp_debit = bank_credit
                    cp_credit = bank_debit

                    bank_move = (
                        self.env["account.move"]
                        .sudo()
                        .create(
                            {
                                "move_type": "entry",
                                "journal_id": bank_journal.id,
                                "date": st_line.date or fields.Date.context_today(self),
                                "ref": rec.name,
                                "line_ids": [
                                    (
                                        0,
                                        0,
                                        {
                                            "name": rec.name,
                                            "account_id": bank_account.id,
                                            "debit": bank_debit,
                                            "credit": bank_credit,
                                        },
                                    ),
                                    (
                                        0,
                                        0,
                                        {
                                            "name": rec.name,
                                            "account_id": rec.clearing_account_id.id,
                                            "debit": cp_debit,
                                            "credit": cp_credit,
                                        },
                                    ),
                                ],
                            }
                        )
                    )
                    bank_move.action_post()
                    # Link the move to the bank statement line so Odoo shows it as matched.
                    st_line.sudo().write({"move_id": bank_move.id})

                # Reconcile clearing account between settlement move and bank move.
                settlement_clearing = move.line_ids.filtered(
                    lambda l: l.account_id == rec.clearing_account_id and not l.reconciled
                )
                bank_clearing = bank_move.line_ids.filtered(
                    lambda l: l.account_id == rec.clearing_account_id and not l.reconciled
                )
                if settlement_clearing and bank_clearing:
                    (settlement_clearing + bank_clearing).reconcile()

                # Finally, mark the statement line as checked so it shows the green tick.
                # (is_reconciled is computed by Odoo once the move exists and lines are reconciled)
                st_line.sudo().write({"checked": True})

            return rec.action_open_form()

    # -------------------------------------------------
    # Action menu helpers (cancel/delete posted entry)
    # -------------------------------------------------
    def action_cancel_posted_entry(self):
        """Cancel the settlement journal entry.

        This is exposed as an *Action* entry in the form view.
        """
        for rec in self:
            if not rec.move_id:
                raise UserError(_("No posted entry to cancel."))
            move = rec.move_id
            # Move must be reset to draft before cancel in most configurations.
            if move.state == "posted":
                move.button_draft()
            if hasattr(move, "button_cancel"):
                move.button_cancel()
            else:
                # Fallback: mark as draft and leave it there.
                rec.message_post(body=_('Posted entry was set back to draft (cancel not available).'))
            rec.state = "imported"
        return True

    def action_delete_posted_entry(self):
        """Delete the settlement journal entry (if allowed by accounting settings)."""
        for rec in self:
            if not rec.move_id:
                raise UserError(_("No posted entry to delete."))
            move = rec.move_id
            # Ensure deletable: draft + not in lock dates, and journal allows it.
            if move.state == "posted":
                move.button_draft()
            # Unlink can be blocked by journal settings / lock dates.
            move_name = move.name
            move.unlink()
            rec.move_id = False
            rec.state = "imported"
            rec.message_post(body=_('Settlement entry %s was deleted.') % (move_name,))
        return True

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


    @api.depends("invoice_id", "invoice_id.amount_total", "invoice_id.amount_total_signed")
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

    def _resolve_links_from_refs(self, vals):
        """Server-side resolver.

        Editable one2many trees and CSV imports may not persist onchange values before a header action
        (e.g. Validate) triggers a record reload. To make the linking robust, we also resolve
        `sale_order_id`/`invoice_id` on create/write when references are provided.
        """
        updates = {}

        # Resolve Sale Order from order_ref
        order_ref = vals.get("order_ref")
        if order_ref:
            so = self.env["sale.order"].search([("name", "=", order_ref)], limit=1)
            if so:
                updates["sale_order_id"] = so.id

        # Resolve Invoice from invoice_reference (exact number) if provided and invoice_id not explicit
        inv_ref = vals.get("invoice_reference")
        if inv_ref and not vals.get("invoice_id"):
            inv = self.env["account.move"].search([
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("name", "=", inv_ref),
                ("company_id", "=", self.env.company.id),
            ], limit=1)
            if inv:
                updates["invoice_id"] = inv.id
        return updates

    @api.model_create_multi
    def create(self, vals_list):
        new_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            vals.update(self._resolve_links_from_refs(vals))
            new_vals_list.append(vals)
        return super().create(new_vals_list)

    def write(self, vals):
        vals = dict(vals)
        vals.update(self._resolve_links_from_refs(vals))
        return super().write(vals)

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

    def unlink(self):
        # Allow deleting settlement lines only while the settlement is in Draft.
        # This is important to avoid altering already validated/posted reconciliations.
        for line in self:
            if line.settlement_id and line.settlement_id.state != "draft":
                raise UserError(_("You can only delete settlement lines while the settlement is in Draft."))
        return super().unlink()

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
