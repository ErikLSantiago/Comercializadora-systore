# -*- coding: utf-8 -*-
{
    'name': 'Website Quote Request',
    'version': '18.0.6.3.12',
    'summary': 'Catálogo /quote con imágenes, filtros, conteo de piezas (build segura para Odoo.sh).',
    'description': 'Publicación en /quote, buscador, filtros (Marca y Categorías), etiqueta Agregado, carrito con total y edición, número de cotización en pantalla de Gracias.',
    'author': 'ChatGPT Assist',
    'website': 'https://example.com',
    'license': 'OPL-1',
    'category': 'Website/CRM',
    'depends': ['product', 'website', 'website_sale', 'sale_management', 'crm', 'mail'],
    'data': [
        'views/product_template_view.xml',
        'views/quote_templates.xml',
    ],
    'images': ['static/description/icon.png'],
    'application': False,
    'installable': True,
}
