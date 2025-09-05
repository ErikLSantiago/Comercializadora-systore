{
    "name": "Adicional Serial Number",
    "summary": "Captura adicional de números de serie por picking/producto sin tocar la trazabilidad nativa.",
    "version": "18.0.1.30.2",
    "author": "Tu Equipo",
    "category": "Inventory/Logistics",
    "license": "LGPL-3",
    "depends": [
        "stock"
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/version.xml",
        "actions/serial_actions.xml",
        "views/serial_views.xml",
        "views/stock_picking_views_inherit.xml"
    ],
    "installable": true,
    "application": false
}