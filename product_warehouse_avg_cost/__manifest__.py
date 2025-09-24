# -*- coding: utf-8 -*-
{
    "name": "Product Warehouse Average Cost (v18)",
    "summary": "Costo promedio por almacén y propuestas de costo (disponibles y total).",
    "version": "18.0.1.4.2",
    "author": "Systore + ChatGPT",
    "website": "https://systore.com.mx",
    "category": "Inventory/Products",
    "depends": ["stock", "product", "purchase"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_views.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
