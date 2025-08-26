# -*- coding: utf-8 -*-
{
    'name': 'Website Quote Request',
    'version': '18.0.6.3.4',
    'summary': 'Permite armar y enviar solicitudes de cotización desde el sitio web sin afectar el flujo nativo.',
    'description': 'Fix: cat.complete_name -> cat.display_name/name en template. Mantiene filtro por categorías públicas y Comentarios -> Notas de la cotización.',
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
