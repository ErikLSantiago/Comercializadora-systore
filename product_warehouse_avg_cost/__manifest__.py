# -*- coding: utf-8 -*-
{
    "name": "Product Warehouse Average Cost (v18)",
    "summary": "Costo promedio por almacén y promedios globales (disponibles y total). Compute robusto para exportaciones masivas.",
    "version": "18.0.1.4.4",
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
