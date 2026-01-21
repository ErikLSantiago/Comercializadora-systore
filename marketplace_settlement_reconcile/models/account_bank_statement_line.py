# -*- coding: utf-8 -*-
from odoo import fields, models, _

class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    marketplace_settlement_id = fields.Many2one(
        "marketplace.settlement",
        string="Marketplace Settlement",
        ondelete="set null",
    )

    def action_open_marketplace_settlement(self):
        self.ensure_one()
        if self.marketplace_settlement_id:
            return self.marketplace_settlement_id.action_open_form()
        settlement = self.env["marketplace.settlement"].create({
            "name": _("Settlement for %s") % (self.payment_ref or self.name or self.date),
            "bank_statement_line_id": self.id,
            "amount_bank": self.amount,
            "currency_id": self.currency_id.id,
        })
        self.marketplace_settlement_id = settlement.id
        return settlement.action_open_form()
