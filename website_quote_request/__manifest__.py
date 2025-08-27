# -*- coding: utf-8 -*-
{
    'name': 'Website Quote Request',
    'version': '18.0.6.3.11',
    'summary': 'Catálogo /quote con imágenes, filtros mejorados, piezas en cotización y botones alineados a la derecha.',
    'description': 'Publicación de productos en /quote, imágenes, buscador, filtros (Marca primero, Categorías segundo), tag Agregado, carrito con edición de cantidades y total de piezas, número de cotización en Gracias.',
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
