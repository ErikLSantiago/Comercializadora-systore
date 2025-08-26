# -*- coding: utf-8 -*-
{
    'name': 'Website Quote Request',
    'version': '18.0.6.3.6',
    'summary': 'Catálogo /quote con buscador, filtros por categorías y variantes, carrito de solicitud y comentarios a Notas.',
    'description': 'Incluye checkbox en Productos para publicar en /quote; buscador, filtros multi-categoría (checkbox) y variantes (prioriza Marca), tag "Agregado" en tarjetas; en Ver solicitud muestra total y edición en línea de cantidades.',
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
