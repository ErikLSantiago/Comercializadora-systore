from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        info = super().session_info()
        if self.env.user.has_group("account.group_account_readonly"):
            info["seller_sales_profit_company_id"] = self.env[
                "account.move.line"
            ]._seller_sales_profit_company_id()
        return info
