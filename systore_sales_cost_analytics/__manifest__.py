# -*- coding: utf-8 -*-
{
    'name': 'Systore - Analítica Ventas, Facturación y Costos',
    'version': '18.0.1.2.0',
    'category': 'Sales/Reporting',
    'summary': 'Concilia facturación, movimientos por lote y órdenes de compra para analizar venta, costo y margen.',
    'author': 'Systore',
    'license': 'LGPL-3',
    'depends': ['web', 'account', 'sale_stock', 'purchase_stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_account_views.xml',
        'wizard/rebuild_wizard_views.xml',
        'views/sales_cost_analytics_views.xml',
        'views/dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'systore_sales_cost_analytics/static/src/js/dashboard.js',
            'systore_sales_cost_analytics/static/src/xml/dashboard.xml',
            'systore_sales_cost_analytics/static/src/css/dashboard.css',
        ],
    },
    'application': True,
    'installable': True,
}
