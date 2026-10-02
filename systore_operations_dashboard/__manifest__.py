{
    'name': 'Systore · Tablero de operaciones',
    'version': '18.0.1.0.2',
    'summary': 'Recepciones, salidas desde existencias y expediciones por almacén',
    'category': 'Inventory/Inventory',
    'author': 'Systore',
    'license': 'LGPL-3',
    'depends': ['web', 'purchase_stock', 'sale_stock'],
    'data': [
        'views/stock_warehouse_views.xml',
        'views/purchase_order_views.xml',
        'views/stock_picking_views.xml',
        'views/dashboard_actions.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'systore_operations_dashboard/static/src/dashboard.js',
            'systore_operations_dashboard/static/src/dashboard.xml',
            'systore_operations_dashboard/static/src/dashboard.scss',
        ],
    },
    'installable': True,
    'application': True,
}
