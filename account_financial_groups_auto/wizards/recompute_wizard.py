from odoo import fields, models


class FinancialGroupRecomputeWizard(models.TransientModel):
    _name = "account.financial.group.recompute.wizard"
    _description = "Recompute Financial Groups"

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    force = fields.Boolean(string="Sobrescribir grupo existente", default=False)
    only_empty = fields.Boolean(string="Solo cuentas sin grupo", default=True)

    def action_recompute(self):
        Account = self.env["account.account"]
        dom = []
        # En algunas localizaciones, account.account puede usar company_ids
        if "company_id" in Account._fields:
            dom.append(("company_id", "=", self.company_id.id))
        elif "company_ids" in Account._fields:
            dom.append(("company_ids", "in", self.company_id.id))

        if self.only_empty:
            dom.append(("financial_group_id", "=", False))

        accounts = Account.search(dom)
        accounts._auto_assign_financial_group(force=self.force)
        return {"type": "ir.actions.act_window_close"}
