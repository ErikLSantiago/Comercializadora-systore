# -*- coding: utf-8 -*-
{
    'name': 'Systore - Costos por Lote / Orden de Compra',
    'version': '18.0.1.0.21',
    'category': 'Inventory/Purchase',
    'summary': 'Reporte operativo de costo por lote ligado a Orden de Compra (sin revalorización contable).',
    'author': 'Systore',
    'license': 'LGPL-3',
    'depends': ['product', 'stock', 'purchase'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_template_views.xml',
        'views/server_actions.xml',
    ],
    'application': False,
    'installable': True,
}
