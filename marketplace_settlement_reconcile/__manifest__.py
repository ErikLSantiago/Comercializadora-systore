# -*- coding: utf-8 -*-
{
    "name": "Marketplace Settlement Reconcile (CSV)",
    "version": "18.0.1.0.3",
    "category": "Accounting",
    "summary": "Mass reconcile marketplace payouts against invoices using CSV settlement lines",
    "author": "Systore",
    "license": "LGPL-3",
    "depends": ["account", "sale_management"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/marketplace_settlement_views.xml",
        "views/account_bank_statement_line_views.xml",
        "wizard/import_settlement_csv_views.xml",
    ],
    "application": False,
    "installable": True,
}
