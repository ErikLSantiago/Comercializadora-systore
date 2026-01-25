{
    "name": "Meat Cutting (Despiece)",
    "version": "18.0.1.0.0",
    "category": "Inventory",
    "summary": "Orden de despiece por peso con costeo contable proporcional (FIFO/lote) y capas por línea.",
    "depends": ["stock", "stock_account", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/stock_picking_type_data.xml",
        "views/meat_cutting_order_views.xml",
    ],
    "installable": True,
    "application": False,
}
