# -*- coding: utf-8 -*-
{
    "name": "Systore Serial Capture (optional)",
    "summary": "Captura opcional de números de serie por operación sin alterar la trazabilidad nativa.",
    "description": "Agrega un botón inteligente en recolección/empaque/salida para capturar N números de serie (ad hoc) y asociarlos a líneas de movimiento (stock.move.line). No modifica el tracking nativo por lote/serie.",
    "version": "18.0.1.0.0",
    "author": "Comercializadora Systore & ChatGPT",
    "website": "https://www.systore.com.mx",
    "category": "Inventory/Operations",
    "license": "LGPL-3",
    "depends": ["stock"],
    "data": [
        "security/ir.model.access.csv",
        "views/serial_capture_menu.xml",
        "views/stock_move_line_serial_views.xml",
        "views/stock_picking_views_inherit.xml",
        "views/serial_capture_wizard_views.xml"
    ],
    "installable": True,
    "application": False
}
