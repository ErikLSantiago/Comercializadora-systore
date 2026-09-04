# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.fields import Datetime

PARAM_KEY = "partner_income_account.cutoff_datetime"


class AccountMove(models.Model):
    _inherit = "account.move"

    def _cutoff_datetime(self):
        val = self.env["ir.config_parameter"].sudo().get_param(PARAM_KEY)
        return Datetime.from_string(val) if val else None

    def _is_after_cutoff(self):
        cutoff = self._cutoff_datetime()
        if not cutoff:
            # Safe default: only apply to records without create_date (created in this tx)
            return self.filtered(lambda m: not m.create_date)
        return self.filtered(lambda m: (not m.create_date) or (m.create_date >= cutoff))

    def _apply_partner_income_account(self):
        moves = self._is_after_cutoff()
        if not moves:
            return

        for move in moves:
            if move.move_type not in ("out_invoice", "out_refund"):
                continue
            if move.state != "draft":
                continue

            income_acc = move.partner_id.systore_income_account_id
            if not income_acc:
                continue

            lines = move.invoice_line_ids.filtered(
                lambda l: not l.display_type and not l.tax_line_id
            )
            if lines:
                lines.write({"account_id": income_acc.id})

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        moves._apply_partner_income_account()
        return moves

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ("partner_id", "invoice_line_ids", "move_type")):
            self._apply_partner_income_account()
        return res

    @api.onchange("partner_id")
    def _onchange_partner_id_apply_income_account(self):
        self._apply_partner_income_account()
