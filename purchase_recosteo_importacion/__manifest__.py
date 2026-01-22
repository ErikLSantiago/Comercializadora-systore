# -*- coding: utf-8 -*-
{
    "name": "Recosteo de Compras (MXN) - Desglose de Costos",
    "version": "18.0.1.1.6",
    "category": "Purchases",
    "summary": "Desglose de costos (USD→MXN) en pestaña dedicada, botón Recostear que impacta price_unit (MXN) y generación de facturas de costos.",
    "author": "Systore",
    "license": "LGPL-3",
    "depends": ["purchase", "product", "account"],
    "data": [
        "views/product_template_views.xml",
        "views/purchase_order_views.xml",
        "views/res_config_settings_views.xml",
        "views/report_purchase_usd_totals.xml",
    ],
    "installable": True,
    "application": False,
}
