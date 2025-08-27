# -*- coding: utf-8 -*-
{
    'name': 'Website Quote Request',
    'version': '18.0.6.3.13',
    'summary': 'Catálogo /quote con filtros, imágenes y acceso controlado por contacto.',
    'description': 'Solo usuarios con el checkbox en Contactos pueden acceder a /quote. Mensaje de no acceso con botones a /contacus y /bussines.',
    'author': 'ChatGPT Assist',
    'website': 'https://example.com',
    'license': 'OPL-1',
    'category': 'Website/CRM',
    'depends': ['product', 'website', 'website_sale', 'sale_management', 'crm', 'mail', 'contacts'],
    'data': [
        'views/product_template_view.xml',
        'views/partner_view.xml',
        'views/quote_templates.xml',
    ],
    'images': ['static/description/icon.png'],
    'application': False,
    'installable': True,
}
