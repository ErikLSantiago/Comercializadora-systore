# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import request, route, Controller
from odoo.http import request
from odoo import fields, http, tools, _
from odoo.addons.website_sale.controllers.variant import WebsiteSaleVariantController




class ProductConfiguratorVisibility(WebsiteSaleVariantController):

    @route('/website_sale/get_combination_info', type='json', auth='public', methods=['POST'], website=True)
    def get_combination_info_website(self, product_template_id, product_id, combination, add_qty, parent_combination=None,**kwargs):
        res = super(ProductConfiguratorVisibility, self).get_combination_info_website(product_template_id, product_id, combination, add_qty, parent_combination=None,
        **kwargs)
        if res and res['product_id']:
            res['quote_variant'] =  True
            visible_product = request.env['product.product'].sudo().browse(res['product_id'])
            if visible_product and visible_product.quote_products:
                res['quote_variant'] = False

        return res
    
       