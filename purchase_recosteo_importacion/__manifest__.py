# -*- coding: utf-8 -*-
{
    'name': 'Recosteo de compras (Importación fija + TC)',
    'version': '18.0.1.0.8',
    'category': 'Purchases',
    'summary': 'Recosteo unitario con importación fija por producto (MXN) y tipo de cambio manual.',
    'description': """Recosteo de compras con tipo de cambio manual, importación fija por producto (MXN) y botón para aplicar al price_unit.""",
    'author': 'Systore',
    'license': 'LGPL-3',
    'depends': ['purchase', 'product'],
    'data': [
        'views/product_template_views.xml',
        'views/purchase_order_views.xml',
        'views/purchase_order_line_views.xml',
    ],
    'installable': True,
    'application': False,
}
