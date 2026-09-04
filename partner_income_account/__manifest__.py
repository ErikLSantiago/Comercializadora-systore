# -*- coding: utf-8 -*-
{
    "name": "Partner Income Account on Invoices",
    "version": "18.0.1.0.4",
    "category": "Accounting",
    "summary": "Assign income account on invoice lines based on customer (partner).",
    "license": "LGPL-3",
    "author": "Systore",
    "depends": ["account", "sale"],
    "data": [
        "views/res_partner_view.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
