# -*- coding: utf-8 -*-
{
    'name': 'Website Quote Request',
    'version': '18.0.6.3.10',
    'summary': 'Catálogo /quote con imágenes, filtros mejorados y conteo de piezas en cotización.',
    'description': 'Publicar productos en /quote, buscador y filtros (Marca primero, Categorías segundo), badge Agregado, edición de cantidades y total de piezas; número de cotización en pantalla de Gracias.',
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
