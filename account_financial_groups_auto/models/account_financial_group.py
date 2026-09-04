from odoo import fields, models

class AccountFinancialGroup(models.Model):
    _name = "account.financial.group"
    _description = "Financial Group (Custom)"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    scope = fields.Selection(
        [
            ("pnl", "P&L (Estado de resultados)"),
            ("balance", "Balance general"),
            ("both", "Ambos"),
        ],
        default="pnl",
        required=True,
    )
