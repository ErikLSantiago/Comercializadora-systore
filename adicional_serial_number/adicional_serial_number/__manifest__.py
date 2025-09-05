# -*- coding: utf-8 -*-
{
    "name": "Adicional Serial Number",
    "summary": "Captura opcional de números de serie por operación sin alterar la trazabilidad nativa.",
    "description": "Agrega un botón inteligente en recolección/empaque/salida (stock.picking) para capturar N números de serie y asociarlos a líneas de movimiento (stock.move.line). No modifica tracking nativo por lote/serie.",
    "version": "18.0.1.8",
    "author": "Comercializadora Systore & ChatGPT",
    "website": "https://www.systore.com.mx",
    "category": "Inventory/Operations",
    "license": "LGPL-3",
    "depends": ["stock"],
    "data": [
        "security/ir.model.access.csv",
        "data/version.xml",
        "views/serial_capture_menu.xml",
        "views/stock_move_line_serial_views.xml",
        "views/stock_picking_views_inherit.xml",
        "views/move_line_list_adicional_sn.xml",
        "views/serial_capture_wizard_views.xml",
        "views/about_views.xml",
        ],
    "installable": True,
    "application": False
}
