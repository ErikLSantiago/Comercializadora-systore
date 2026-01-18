{
    'name': 'Recosteo de Compras (MXN) - Desglose de Costos',
    'version': '18.0.1.0.3',
    'category': 'Purchases',
    'summary': 'Desglose de costos (USD→MXN) en pestaña dedicada y botón Recostear que impacta price_unit (MXN).',
    'author': 'Systore',
    'license': 'LGPL-3',
    'depends': ['purchase', 'product'],
    'data': [
        'views/product_template_views.xml',
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'application': False,
}
