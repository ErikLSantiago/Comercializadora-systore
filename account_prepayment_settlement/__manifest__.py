{
    "name": "Prepayment Settlement for Invoices",
    "version": "18.0.1.2.0",
    "category": "Accounting",
    "summary": "Pay vendor bills/customer invoices using asset/liability prepayment accounts (no bank).",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "views/prepayment_apply_wizard_view.xml",
        "views/account_move_view.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
