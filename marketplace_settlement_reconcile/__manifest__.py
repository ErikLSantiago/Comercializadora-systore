# -*- coding: utf-8 -*-
{
    "name": "Marketplace Settlement Reconcile (CSV)",
    "version": "18.0.1.0.32",
    "category": "Accounting",
    "summary": "Mass reconcile marketplace payouts against invoices using CSV settlement lines",
    "author": "Systore",
    "license": "LGPL-3",
    "depends": ["account", "account_accountant", "sale_management"],
    "data": [
        "security/ir.model.access.csv",
        "security/marketplace_settlement_security.xml",
        "views/res_config_settings_views.xml",
        "wizard/import_settlement_csv_views.xml",
        "views/marketplace_settlement_views.xml",
        "views/marketplace_settlement_server_actions.xml",
        "views/bank_rec_widget_quick_create_views.xml",
        "views/bank_rec_widget_kanban_views.xml",
    ],
    "application": False,
    "installable": True,
}