# -*- coding: utf-8 -*-
{
    "name": "PDF IVA 16% en Cotizaciones y Órdenes (solo presentación)",
    "summary": "Recalcula y muestra IVA 16% únicamente en los PDF de ventas y compras, sin afectar contabilidad.",
    "version": "18.0.1.0.0",
    "author": "ChatGPT",
    "website": "https://example.com",
    "license": "LGPL-3",
    "category": "Reporting",
    "depends": ["sale", "purchase"],
    "data": [
        "report/iva_display_templates.xml",
    ],
    "application": False,
    "installable": True,
}