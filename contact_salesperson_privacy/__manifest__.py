{
    "name": "Contact Privacy by Salesperson",
    "summary": "Restrict private contacts to assigned salespeople",
    "version": "18.0.1.2.0",
    "category": "Sales/CRM",
    "author": "Systore",
    "license": "LGPL-3",
    "depends": ["contacts", "sale_management"],
    "data": [
        "security/contact_privacy_security.xml",
        "views/res_partner_views.xml",
        "views/res_users_views.xml",
        "views/contact_privacy_menu.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
