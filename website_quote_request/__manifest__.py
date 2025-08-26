
# -*- coding: utf-8 -*-
{
    'name': 'Website Quote Request',
    'version': '18.0.6.3.3',
    'summary': 'Permite armar y enviar solicitudes de cotización desde el sitio web sin afectar el flujo nativo.',
    'description': 'Flujo completo para armar solicitudes de cotización desde el Website con productos publicados, filtro por categorías públicas (public_categ_id), carrito propio, página "Ver solicitud" con campo Comentarios y creación de cotización (sale.order). Los comentarios se publican en Notas de la cotización.',
    'author': 'ChatGPT Assist',
    'website': 'https://example.com',
    'license': 'OPL-1',
    'category': 'Website/CRM',
    'depends': ['website', 'website_sale', 'sale_management', 'crm', 'mail'],
    'data': [
        'views/quote_templates.xml',
    ],
    'images': ['static/description/icon.png'],
    'application': False,
    'installable': True,
}
