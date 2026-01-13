# -*- coding: utf-8 -*-
from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _prepare_invoice_line(self, **optional_values):
        vals = super()._prepare_invoice_line(**optional_values)

        order = self.order_id
        partner = order.partner_invoice_id or order.partner_id
        income_acc = partner.systore_income_account_id

        # Solo si el partner tiene cuenta definida y estamos generando una factura de cliente
        # (en venta estándar, esto será out_invoice).
        if income_acc:
            vals["account_id"] = income_acc.id

        return vals
