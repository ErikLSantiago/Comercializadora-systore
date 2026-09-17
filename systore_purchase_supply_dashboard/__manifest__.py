{
    "name": "Systore - Tablero de Compras y Abastecimiento",
    "version": "18.0.1.6.0",
    "category": "Inventory/Purchase",
    "summary": "Conciliación de compras, recepciones, demanda, lotes y pagos manuales",
    "author": "Systore",
    "license": "LGPL-3",
    "depends": [
        "purchase_stock",
        "sale_stock",
        "web",
        "purchase_recosteo_importacion",
        "wholesale_allocation",
        "stock_upc_validation",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/supply_dashboard_views.xml",
        "views/purchase_order_views.xml",
        "views/stock_warehouse_views.xml",
        "views/supply_dashboard_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "systore_purchase_supply_dashboard/static/src/js/supply_dashboard.js",
            "systore_purchase_supply_dashboard/static/src/xml/supply_dashboard.xml",
            "systore_purchase_supply_dashboard/static/src/scss/supply_dashboard.scss",
        ],
    },
    "application": True,
    "installable": True,
}
