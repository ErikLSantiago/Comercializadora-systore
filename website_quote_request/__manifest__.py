# -*- coding: utf-8 -*-
{
    'name': 'Website Quote Request',
    'version': '18.0.6.3.11',
    'summary': 'Catálogo /quote con imágenes, filtros mejorados, piezas en cotización y botones alineados a la derecha en /quote/cart.',
    'description': 'Alinea “Enviar cotización” y “Seguir agregando productos” al lado inferior derecho en /quote/cart.',
    'author': 'ChatGPT Assist',
    'website': 'https://example.com',
    'license': 'OPL-1',
    'category': 'Website/CRM',
    'depends': ['product', 'website', 'website_sale', 'sale_management', 'crm', 'mail'],
    'data': [
        'views/product_template_view.xml',
        'views/sale_order_view.xml',
        'views/quote_templates.xml',
    ],
    'images': ['static/description/icon.png'],
    'application': False,
    'installable': True,
}
