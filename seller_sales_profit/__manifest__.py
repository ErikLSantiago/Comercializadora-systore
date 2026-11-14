{
    "name": "Utilidad por ventas de sellers",
    "version": "18.0.1.0.0",
    "summary": "Tablero contable de utilidad por seller",
    "category": "Accounting/Accounting",
    "license": "LGPL-3",
    "depends": ["account", "web"],
    "data": ["views/dashboard_menu.xml"],
    "assets": {
        "web.assets_backend": [
            "seller_sales_profit/static/src/dashboard.js",
            "seller_sales_profit/static/src/dashboard.xml",
        ],
    },
    "installable": True,
}
