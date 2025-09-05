# -*- coding: utf-8 -*-
{
    "name": "Operaciones: Enviar por correo (Stock Picking)",
    "summary": "Botón para enviar por correo desde operaciones de almacén y plantilla favorita.",
    "version": "18.0.1.0.0",
    "author": "Comercializadora Systore & ChatGPT",
    "license": "LGPL-3",
    "website": "https://systore.com.mx",
    "category": "Inventory/Inventory",
    "depends": ["stock", "mail"],
    "data": [
        "data/mail_template_data.xml",
        "views/stock_picking_views.xml",
        "views/mail_template_views.xml",
        "views/menus.xml"
    ],
    "installable": True,
    "application": False,
}