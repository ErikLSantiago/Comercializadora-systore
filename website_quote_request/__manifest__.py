# -*- coding: utf-8 -*-
{
    'name': 'Website Quote Request',
    'version': '18.0.6.3.8',
    'summary': 'Catálogo /quote con imágenes, buscador, filtros, carrito y número de cotización en la pantalla de Gracias.',
    'description': 'Muestra imagen del producto en /quote y despliega el número de cotización generado en la pantalla de Gracias. Incluye checkbox Publicar en /quote y filtros por categorías públicas y variantes.',
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
