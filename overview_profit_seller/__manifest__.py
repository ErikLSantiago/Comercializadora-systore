{
    "name": "overview_profit_seller",
    "version": "18.0.1.9.0",
    "summary": "Tablero contable de utilidad por seller",
    "category": "Accounting/Accounting",
    "license": "LGPL-3",
    "depends": ["account", "web"],
    "data": ["views/res_partner_views.xml", "views/dashboard_menu.xml", "views/res_config_settings_views.xml"],
    "assets": {
        "web.assets_backend": [
            "overview_profit_seller/static/src/menu_visibility.js",
            "overview_profit_seller/static/src/dashboard.js",
            "overview_profit_seller/static/src/dashboard.xml",
        ],
    },
    "installable": True,
}
