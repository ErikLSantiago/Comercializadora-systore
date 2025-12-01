# -*- coding: utf-8 -*-
{
    "name": "Systore Warranty Sale-Purchase Bridge",
    "summary": "Vincula tickets de garantía con pedidos de venta y genera órdenes de compra en Scrap Systore.",
    "version": "18.0.1.0.3",
    "author": "Comercializadora Systore",
    "website": "https://systore.com.mx",
    "license": "LGPL-3",
    "category": "Sales",
    "depends": [
        "sale_management",
        "purchase",
        "helpdesk",
        "systore_warranty_helpdesk"
    ],
    "data": [
        "views/sale_order_views.xml"
    ],
    "installable": True,
    "application": False
}