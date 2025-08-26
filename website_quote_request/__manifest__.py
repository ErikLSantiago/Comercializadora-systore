# -*- coding: utf-8 -*-
{
    "name": "Website Quote Request",
    "version": "18.0.6.2.1",
    "summary": "Permite a visitantes armar y enviar solicitudes de cotización desde el sitio web sin afectar el flujo nativo.",
    "category": "Website",
    "author": "ChatGPT Assist",
    "license": "OEEL-1",
    "depends": ["website", "sale", "portal"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_views.xml",
        "views/quote_templates.xml"
        "views/public_categ_filter.xml"
    ],
    "installable": True,
    "application": False,
    "post_init_hook": "post_init",
}
