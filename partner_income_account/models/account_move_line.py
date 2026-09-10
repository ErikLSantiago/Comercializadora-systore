# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.fields import Datetime

PARAM_KEY = "partner_income_account.cutoff_datetime"


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _cutoff_datetime(self):
        val = self.env["ir.config_parameter"].sudo().get_param(PARAM_KEY)
        return Datetime.from_string(val) if val else None

    @api.depends(
        "move_id.partner_id",
        "move_id.partner_id.systore_income_account_id",
        "move_id.move_type",
        "move_id.create_date",
        "move_id.state",
        "display_type",
        "product_id",
    )
    def _compute_account_id(self):
        super()._compute_account_id()

        cutoff = self._cutoff_datetime()

        for line in self:
            move = line.move_id
            if not move:
                continue

            # Not retroactive: skip invoices created before cutoff
            if cutoff and move.create_date and move.create_date < cutoff:
                continue

            if move.move_type not in ("out_invoice", "out_refund"):
                continue

            if move.state != "draft":
                continue

            if line.display_type or line.tax_line_id:
                continue

            income_acc = move.partner_id.systore_income_account_id
            if not income_acc:
                continue

            line.account_id = income_acc
