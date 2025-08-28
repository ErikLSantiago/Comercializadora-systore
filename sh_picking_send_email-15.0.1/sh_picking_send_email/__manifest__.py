# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
{
    "name": "Picking Send By Email",
    "author": "Softhealer Technologies",
    "support": "support@softhealer.com",
    "website": "https://www.softhealer.com",
    "category": "Warehouse",
    "summary": " Picking Order By Email Module, Email Picking Order Detail,Warehouse product Details In Email, Product Detail Email,Picking Order Information Email, Product Stock mail Odoo ",
    "description": """
    Currently in odoo email sent to customer don't have full details of the picking order, they need to download pdf and see picking order details, our module help to show full picking order detail so the customer can quickly see picking order details directly in an email itself.
Picking Order Details Email Odoo
 Send Picking Order By Email Module, Warehouse product Details In Email, Product Detail Email,Stock Information Email, Product Picking Order mail Odoo 
 Picking Order By Email Module, Email Picking Order Detail,Warehouse product Details In Email, Product Detail Email,Picking Order Information Email, Product Stock mail Odoo 
    """,
    "version": "15.0.1",
    "depends": [
        'stock'
    ],
    "data": [
        'data/stock_email_data.xml',
        'views/stock_picking_view.xml',
    ],
    "images": ['static/description/background.png', ],
    "live_test_url": "https://youtu.be/2CPVI_cstlk",
    "license": "OPL-1",
    "auto_install": False,
    "application": True,
    "installable": True,
    "price": "25",
    "currency": "EUR"
}
