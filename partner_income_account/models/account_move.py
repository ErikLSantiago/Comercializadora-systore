# -*- coding: utf-8 -*-
from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _apply_partner_income_account(self):
        for move in self:
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
