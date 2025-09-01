# -*- coding: utf-8 -*-
{
    "name": "PDF IVA 16% - Sin IVA en formulario + Reporte nuevo (Ventas/Compras)",
    "summary": "Añade columnas y totales 'Sin IVA' en formularios de venta/compra y un nuevo PDF imprimible independiente.",
    "version": "18.0.1.1.3",
    "author": "ChatGPT",
    "website": "https://example.com",
    "license": "LGPL-3",
    "category": "Reporting",
    "depends": ["sale_management", "purchase"],
    "data": [
        "views/sale_sin_iva_views.xml",
        "views/purchase_sin_iva_views.xml",
        "report/sin_iva_reports.xml"
    ],
    "installable": True,
    "application": False
}