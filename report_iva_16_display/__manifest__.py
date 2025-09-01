# -*- coding: utf-8 -*-
{
    "name": "PDF IVA 16% en Cotizaciones y Órdenes (solo presentación)",
    "summary": "Inserta debajo de los totales un resumen con IVA 16% en los PDF de ventas y compras (anclado a t-call de totales).",
    "version": "18.0.1.0.5",
    "author": "ChatGPT",
    "website": "https://example.com",
    "license": "LGPL-3",
    "category": "Reporting",
    "depends": ["sale", "purchase"],
    "data": [
        "report/iva_display_templates.xml"
    ],
    "installable": True,
    "application": False
}