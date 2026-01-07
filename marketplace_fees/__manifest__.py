# -*- coding: utf-8 -*-
{
    "name": "Marketplace Fees",
    "summary": "Comisiones y envío por marketplace (Producteca) + cuenta de ventas por marketplace",
    "description": "Agrega líneas de comisión (%) y envío fijo por producto al confirmar ventas cuando la orden tiene canal/binding y el producto posee configuración. Permite definir una cuenta de ingresos por marketplace. Selector simple a producteca.channel. Textos en español.",
    "version": "18.0.1.6.3",
    "author": "Systore + ChatGPT",
    "license": "OEEL-1",
    "website": "https://www.systore.com.mx",
    "category": "Ventas/Contabilidad",
    "depends": ["sale_management", "account", "product", "odoo_connector_api_producteca"],
    "data": [
        "security/ir.model.access.csv",
        "views/fee_config_views.xml",
        "views/product_views.xml"
    ],
    "installable": True,
    "application": False
}