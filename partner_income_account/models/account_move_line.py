# -*- coding: utf-8 -*-
from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.depends(
        "move_id.partner_id",
        "move_id.partner_id.systore_income_account_id",
        "move_id.move_type",
        "display_type",
        "product_id",
    )
    def _compute_account_id(self):
        super()._compute_account_id()

        for line in self:
            move = line.move_id
            partner = move.partner_id

            if not move:
                continue

            if move.move_type not in ("out_invoice", "out_refund"):
                continue

            if move.state != "draft":
                continue

            if line.display_type or line.tax_line_id:
                continue

            income_acc = partner.systore_income_account_id
            if not income_acc:
                continue

            line.account_id = income_acc
