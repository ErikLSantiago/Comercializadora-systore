# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    mkp_income_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de ingresos",
        domain="[('deprecated', '=', False), ('account_type', '=', 'income')]",
        company_dependent=True,
        help="Cuenta de ingresos a utilizar en facturas cuando este contacto sea el Seller de la orden de venta.",
    )
