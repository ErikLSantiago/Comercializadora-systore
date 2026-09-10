# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ResCompany(models.Model):
    _inherit = "res.company"

    mkp_clearing_account_id = fields.Many2one(
        "account.account",
        string="Marketplace Clearing Account",
        help="Temporary clearing account used to match the bank deposit (net).",
    )
    mkp_settlement_journal_id = fields.Many2one(
        "account.journal",
        string="Marketplace Settlement Journal",
        help="Journal used to post settlement entries (credits receivable, debits clearing/expenses).",
        domain=[("type", "=", "general")],
    )

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    mkp_clearing_account_id = fields.Many2one(
        related="company_id.mkp_clearing_account_id",
        readonly=False,
    )
    mkp_settlement_journal_id = fields.Many2one(
        related="company_id.mkp_settlement_journal_id",
        readonly=False,
    )
