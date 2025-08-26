# -*- coding: utf-8 -*-
{
    'name': 'Website Quote Request',
    'version': '18.0.6.3.9',
    'summary': 'Catálogo /quote con imágenes, buscador, filtros mejorados, carrito y número de cotización en Gracias.',
    'description': 'Añade botón "Limpiar filtros", coloca Categorías como segundo bloque de filtros (después de Marca) y muestra el tag "Agregado" debajo del nombre del producto.',
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
