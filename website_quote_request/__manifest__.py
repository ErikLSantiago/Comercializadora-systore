# -*- coding: utf-8 -*-
{
    'name': 'Website Quote Request',
    'version': '18.0.6.3.2',
    'summary': 'Permite armar y enviar solicitudes de cotización desde el sitio web sin afectar el flujo nativo.',
    'description': 'Formulario de cotización desde Website que crea oportunidades en CRM y permite adjuntos. Incluye campo Comentarios que se publica en Notas de la cotización y soporte a categorías públicas.',
    'author': 'ChatGPT Assist',
    'website': 'https://example.com',
    'license': 'OPL-1',
    'category': 'Website/CRM',
    'depends': ['website', 'crm', 'mail', 'website_sale'],
    'data': [
        'views/quote_templates.xml',
    ],
    'images': ['static/description/icon.png'],
    'application': False,
    'installable': True,
}
