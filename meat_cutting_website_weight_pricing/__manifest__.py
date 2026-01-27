# -*- coding: utf-8 -*-
{
    "name": "Meat Cutting - Website Weight Pricing (Checkout Reservation)",
    "version": "1.0.2",
    "category": "Sales/Website",
    "summary": "Show price per weight on website and reserve lots at checkout to compute exact price.",
    "depends": ["website_sale", "sale_stock", "stock", "meat_cutting", "meat_cutting_weight_sale_price"],
    "data": ["security/ir.model.access.csv", "data/cron.xml", "views/product_views.xml", "views/website_sale_templates.xml"],
    "assets": {"web.assets_frontend": ["meat_cutting_website_weight_pricing/static/src/js/mc_web_move_lot_summary.js"]},
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
