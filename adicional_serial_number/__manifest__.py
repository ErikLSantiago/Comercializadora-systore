# -*- coding: utf-8 -*-
{
    "name": "Adicional Serial Number",
    "summary": "Captura opcional de números de serie por operación sin alterar la trazabilidad nativa.",
    "description": "Botón por picking y por línea para pegar múltiples números de serie y asociarlos a líneas de movimiento. Reporte con filtros y edición mientras la operación no esté validada.",
    "version": "18.0.1.30",
    "author": "Comercializadora Systore & ChatGPT",
    "website": "https://www.systore.com.mx",
    "category": "Inventory/Operations",
    "license": "LGPL-3",
    "depends": ["stock"],
    "data": [
        "actions/serial_actions.xml",
        "security/ir.model.access.csv",
        "data/version.xml",
        "views/serial_capture_menu.xml",
        "views/stock_move_line_serial_views.xml",
        "views/stock_picking_views_inherit.xml",
        "views/serial_capture_wizard_views.xml",
        "views/move_line_list_adicional_sn.xml",
        "views/about_views.xml"
    ],
    "installable": True,
    "application": False
}
