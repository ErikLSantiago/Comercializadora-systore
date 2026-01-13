# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
from odoo.fields import Datetime

PARAM_KEY = "partner_income_account.cutoff_datetime"

def post_init_hook(cr, registry):
    """Store a cutoff datetime so the module is NOT retroactive.

    Any invoice created BEFORE this cutoff will be ignored by the enforcement logic.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    icp = env["ir.config_parameter"].sudo()
    if not icp.get_param(PARAM_KEY):
        icp.set_param(PARAM_KEY, Datetime.to_string(Datetime.now()))
