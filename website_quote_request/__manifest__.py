# -*- coding: utf-8 -*-
{
    "name": "Website Quote Request",
    "version": "18.0.6.3.0",
    "summary": "Permite a visitantes armar y enviar solicitudes de cotización desde el sitio web sin afectar el flujo nativo.",
    "category": "Website",
    "author": "ChatGPT Assist",
    "license": "OEEL-1",
    "depends": ["website", "sale", "portal", "website_sale"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_views.xml",
        "views/quote_templates.xml"
    ],
    "installable": True,
    "application": False,
    "post_init_hook": "post_init",
}
