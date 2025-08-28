# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.addons.website.models import ir_http
from odoo.http import request


class ProductTemplate(models.Model):
    _inherit = "product.template"

    quote_products = fields.Boolean('Quote Products', default=False)


class ProductProduct(models.Model):
    _inherit = "product.product"

    quote_prod = fields.Boolean('quote products ', inverse='set_quote_products')
    quote_products = fields.Boolean('Quote Products', compute='_compute_quote_products',inverse='set_quote_products', readonly=False, store=True)

    @api.depends('quote_products')
    def _compute_quote_products(self):
        for rec in self:
            rec.quote_products = rec.quote_prod
            if len(rec.product_tmpl_id.product_variant_ids) > 1:
                if any(tmpl_variant.quote_products for tmpl_variant in rec.product_tmpl_id.product_variant_ids):
                    rec.product_tmpl_id.quote_products = True
                else:
                    rec.product_tmpl_id.quote_products = False
            else:
                rec.product_tmpl_id.quote_products = rec.quote_products

    def set_quote_products(self):
        for rec in self:
            if rec.quote_products:
                rec.product_tmpl_id.quote_products = rec.quote_products



class Website(models.Model):
    _inherit = 'website'

    def get_quote_products(self, website_id=None):
        current_website = request.website
        quote_ids = self.env['product.template'].sudo().search([
            ('quote_products', '=', 'True'),
            '|',
            ('website_id', '=', False),
            ('website_id', 'in', current_website.ids),
        ])
        return quote_ids

    def get_qty(self):
        res = 0
        if request.session['uid']:
            quote_cart_ids = self.env['quote.order'].sudo().search([('partner_id', '=', self.env.user.partner_id.id)])
            request.session['quote_order_id'] = quote_cart_ids.id
        else:
            if 'quote_order_id' in request.session.keys():
                quote_cart_ids = self.env['quote.order'].sudo().browse(request.session['quote_order_id'])
            else:
                quote_cart_ids = self.env['quote.order'].sudo().browse(None)

        for i in quote_cart_ids.quote_lines:
            res = res + i.qty
        return int(res)

    def get_quote_cart_products(self):
        order = self.env['quote.order'].sudo().search([])
        quote_cart_ids = self.env['quote.order'].sudo().browse(request.session['quote_order_id'])

        return quote_cart_ids.quote_lines


class QuoteOrderLine(models.Model):
    _name = 'quote.order.line'
    _description = "Quote Order Line"

    product_id = fields.Many2one('product.product')
    qty = fields.Float('Quantity')
    price = fields.Float('Price')
    quote_id = fields.Many2one('quote.order', 'Quote Order')

    def unlink(self):
        return super(QuoteOrderLine, self).unlink()


class QuoteOrder(models.Model):
    _name = 'quote.order'
    _description = "Quote Order"

    partner_id = fields.Many2one('res.partner')
    quote_lines = fields.One2many('quote.order.line', 'quote_id', 'Quote Lines')

    def unlink(self):
        for qt in self:
            qt.sudo().quote_lines.unlink()
        return super(QuoteOrder, self).unlink()


class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'

    last_website_quote_id = fields.Many2one('quote.order', compute='_compute_last_website_quote_id',
                                            string='Last Online Sales Order.')

    def _compute_last_website_quote_id(self):
        QuoteOrder = self.env['quote.order']
        for partner in self:
            is_public = any([u._is_public()
                             for u in partner.with_context(active_test=False).user_ids])
            website = ir_http.get_request_website()
            if website and not is_public:
                partner.last_website_quote_id = QuoteOrder.search([
                    ('partner_id', '=', partner.id),
                ], order='id desc', limit=1)
            else:
                partner.last_website_quote_id = QuoteOrder
