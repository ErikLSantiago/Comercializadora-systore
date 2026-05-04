{
    'name': 'Wholesale Allocation',
    'version': '18.0.1.3.0',
    'summary': 'Restrict auto reservation by associated purchase orders for wholesale sales',
    'description': """
Wholesale Allocation
====================

Phase 1 for wholesale operations:
- Add associated purchase orders on sales orders.
- Restrict automatic reservation to lots whose name matches the associated PO number.
- Allow manual use of external lots on delivery operations.
- Apply only to warehouses marked as Wholesale.
    """,
    'author': 'OpenAI',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'purchase', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_warehouse_views.xml',
        'views/sale_order_views.xml',
        'views/sale_order_confirm_warning_views.xml',
        'views/stock_picking_views.xml',
    ],
    'installable': True,
    'application': False,
}
