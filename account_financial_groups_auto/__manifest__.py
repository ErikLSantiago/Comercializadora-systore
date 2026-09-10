{
    "name": "Financial Groups (Auto) for Reports - Odoo 18",
    "version": "18.0.1.1.0",
    "category": "Accounting",
    "summary": "Custom financial groups with auto-assignment rules for safer P&L/Balance grouping.",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "security/ir_rules.xml",
        "views/account_financial_group_views.xml",
        "views/account_financial_group_rule_views.xml",
        "views/account_account_views.xml",
        "wizards/recompute_wizard_views.xml",
    ],
    "installable": True,
    "application": False
}
