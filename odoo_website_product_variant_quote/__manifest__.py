# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Website Get Quote Shop for Product Variant',
    'version': '18.0.0.0',
    'category': 'eCommerce',
    'license': 'OPL-1',
    'summary': 'Get Quote Web Design Form Template website ask for quote website Request for quotation Website Product Quote website request quote shop Get a Quote website Get Quote shop Product variant Quote Request for quote Website Quote Request A Quote for products',
    "description": """
This odoo app helps user to get quote from website shop for product variants with login or non login user and crate customer for non login user. User can configure quote product varinat sna see this product on get quote shop, add to cart quote variants, increase or decrease quantity and create quote, if user not logged in then customer will created from details with quote.
    """,
    'author': 'BROWSEINFO',
    'website': 'https://www.browseinfo.com/demo-request?app=odoo_website_product_variant_quote&version=18&edition=Community',
    "price": 35,
    "currency": 'EUR',
    'depends': ['website', 'website_sale', 'sale_management'],
    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/product_view.xml',
        'views/templates.xml',
    ],
    'qweb': [],
    "auto_install": False,
    "installable": True,
    "live_test_url": 'https://www.browseinfo.com/demo-request?app=odoo_website_product_variant_quote&version=18&edition=Community',
    "images": ["static/description/Banner.gif"],
    'assets':{
        'web.assets_frontend':[
            'odoo_website_product_variant_quote/static/src/js/web.js',
        ]
    },
    'license': 'OPL-1',
}
