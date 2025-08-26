# -*- coding: utf-8 -*-
{
    'name': 'Website Quote Request',
    'version': '18.0.6.3.5',
    'summary': 'Permite armar y enviar solicitudes de cotización desde el sitio web sin afectar el flujo nativo.',
    'description': 'Patch: QWeb fix (replace getattr with cat.display_name). Mantiene filtro por categorías públicas, carrito, y Comentarios -> Notas.',
    'author': 'ChatGPT Assist',
    'website': 'https://example.com',
    'license': 'OPL-1',
    'category': 'Website/CRM',
    'depends': ['website', 'website_sale', 'sale_management', 'crm', 'mail'],
    'data': ['views/quote_templates.xml'],
    'images': ['static/description/icon.png'],
    'application': False,
    'installable': True,
}
