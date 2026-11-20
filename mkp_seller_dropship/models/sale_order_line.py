# -*- coding: utf-8 -*-
from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _prepare_invoice_line(self, **optional_values):
        vals = super()._prepare_invoice_line(**optional_values)
        seller = self.order_id._mkp_get_seller()
        if seller and seller.mkp_income_account_id:
            vals["account_id"] = seller.mkp_income_account_id.id
        return vals
