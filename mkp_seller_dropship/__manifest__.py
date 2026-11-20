# -*- coding: utf-8 -*-
{
    "name": "Marketplace Seller Dropship Bridge",
    "version": "18.0.1.7.0",
    "summary": "Seller stock sale bridge with commercial PO and consolidated invoicing",
    "category": "Sales",
    "author": "Custom",
    "license": "LGPL-3",
    "depends": [
        "sale_stock",
        "purchase_stock",
        "stock_dropshipping",
        "account",
        "stock_sellers",
        "seller_infrastructure",
    ],
    "data": [
        "views/sale_order_views.xml",
        "views/account_move_views.xml",
        "views/purchase_order_views.xml",
        "views/res_partner_views.xml",
    ],
    "application": False,
    "installable": True,
}
