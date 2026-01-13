# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    systore_income_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta de ingresos",
        company_dependent=True,
        domain="[('account_type', 'in', ('income', 'income_other')), ('deprecated', '=', False)]",
        help="Si se configura, las facturas de este cliente usarán esta cuenta en sus líneas de ingreso.",
    )
