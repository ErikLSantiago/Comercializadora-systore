{
    'name': 'Systore - Surplus Route',
    'version': '18.0.1.1.0',
    'summary': 'Añade la acción Surplus a las reglas de inventario de Odoo',
    'description': """
Systore - Surplus Route
=======================

Añade una acción configurable ``Surplus`` a ``stock.rule``.

Cuando una operación deja mercancía en la ubicación origen de una regla
Surplus, el módulo:
- deja que Odoo termine el movimiento normal;
- reintenta primero las reservas de la demanda pendiente que consume esa ubicación;
- respeta cualquier extensión del motor de reservas, incluyendo Wholesale Allocation;
- calcula únicamente el excedente atribuible a la llegada que acaba de validarse;
- crea y reserva la operación configurada en la propia regla por la cantidad sobrante;
- conserva el lote/serie de la llegada en productos rastreados.

La configuración vive en Rutas/Reglas, no en el almacén, por lo que la misma
lógica puede reutilizarse en otros almacenes y flujos.
    """,
    'author': 'OpenAI',
    'license': 'LGPL-3',
    'depends': [
        'stock',
    ],
    'data': [
        'views/stock_rule_views.xml',
        'views/stock_picking_views.xml',
        # Se conserva inactiva para facilitar la actualización desde 18.0.1.0.0.
        'views/stock_warehouse_views.xml',
    ],
    'installable': True,
    'application': False,
}
