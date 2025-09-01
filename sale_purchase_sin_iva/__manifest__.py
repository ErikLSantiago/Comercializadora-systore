# -*- coding: utf-8 -*-
{
    "name": "Sin IVA en formulario + Reporte nuevo (Ventas/Compras)",
    "summary": "Añade columna 'Sin IVA' en líneas y un nuevo reporte PDF con Subtotal/IVA(16%)/Total calculados a partir de precio sin IVA.",
    "version": "18.0.1.1.8",
    "category": "Reporting",
    "author": "ChatGPT",
    "website": "https://example.com",
    "license": "LGPL-3",
    "depends": ["sale_management", "purchase"],
    "data": [
        "views/sale_sin_iva_views.xml",
        "views/purchase_sin_iva_views.xml",
        "report/sin_iva_reports.xml",
    ],
    "assets": {},
    "installable": True,
    "application": False,
}
