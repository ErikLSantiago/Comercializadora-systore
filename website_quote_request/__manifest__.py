# -*- coding: utf-8 -*-
{
    'name': 'Website Quote Request',
    'version': '18.0.6.3.7',
    'summary': 'Catálogo /quote con buscador, filtros, carrito y comentarios a Notas.',
    'description': 'Incluye checkbox en Productos para publicar en /quote; buscador, filtros multi-categoría y por variantes (Marca primero); tag Agregado; Ver solicitud con total y edición inline. Vista robusta que añade un tab propio en el formulario de producto.',
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
