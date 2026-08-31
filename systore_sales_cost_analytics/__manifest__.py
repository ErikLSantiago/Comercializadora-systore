# -*- coding: utf-8 -*-
{
    'name': 'Systore - Analítica Ventas, Facturación y Costos',
    'version': '18.0.1.0.0',
    'category': 'Sales/Reporting',
    'summary': 'Concilia facturación, movimientos por lote y órdenes de compra para analizar venta, costo y margen.',
    'author': 'Systore',
    'license': 'LGPL-3',
    'depends': ['account', 'sale_stock', 'purchase_stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_account_views.xml',
        'wizard/rebuild_wizard_views.xml',
        'views/sales_cost_analytics_views.xml',
    ],
    'application': True,
    'installable': True,
}
