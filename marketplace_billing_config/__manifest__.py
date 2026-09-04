# -*- coding: utf-8 -*-
{
    "name": "Marketplace Billing Config",
    "summary": "Configura por marketplace el contacto de facturación y la cuenta de ingresos (Producteca)",
    "description": "Permite definir por canal de venta/marketplace (Producteca) un contacto de facturación y una cuenta de ingresos. "
                   "Al asignar el canal en la orden de venta, precarga la dirección de factura; y al generar factura, "
                   "fuerza la cuenta de ingresos en las líneas según el canal.",
    "version": "18.0.1.1.0",
    "author": "Systore + ChatGPT",
    "license": "OEEL-1",
    "website": "https://www.systore.com.mx",
    "category": "Ventas/Contabilidad",
    "depends": ["sale_management", "account", "odoo_connector_api_producteca"],
    "data": [
        "security/ir.model.access.csv",
        "views/marketplace_billing_config_views.xml",
],
    "installable": True,
    "application": False
,
    'post_init_hook': 'post_init_hook',
}
