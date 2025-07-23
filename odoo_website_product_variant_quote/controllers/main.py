# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import datetime
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
import json
import logging
from odoo import fields, http, tools, _
from odoo.http import request, content_disposition
from odoo.addons.base.models.ir_qweb_fields import nl2br
from odoo.addons.website.controllers.main import QueryURL
from odoo.exceptions import ValidationError
from odoo.addons.website.controllers.main import Website
from odoo.addons.website_sale.controllers.main import TableCompute,WebsiteSale
from odoo.osv import expression
from odoo.tools.misc import formatLang, format_date

_logger = logging.getLogger(__name__)

PPG = 20  # Products Per Page
PPR = 4   # Products Per Row



class OdooWebsiteProductQuote(http.Controller):

	def _get_search_domain(self, search,avail_prods):
		web_domain = request.website.get_current_website().website_domain()
		domains = [[("sale_ok", "=", True)]]
		domains.append(web_domain)
		domains.append([('id','in',avail_prods)])
		domains.append([('website_published','=',True)])
		if search:
			for srch in search.split(" "):
				subdomains = [
					[('name', 'ilike', srch)],
					[('product_variant_ids.default_code', 'ilike', srch)]
				]
				subdomains.append([('description', 'ilike', srch)])
				subdomains.append([('description_sale', 'ilike', srch)])
				domains.append(expression.OR(subdomains))

		return expression.AND(domains)

	def _get_pricelist_context(self):
		pricelist_context = dict(request.env.context)
		pricelist = False
		if not pricelist_context.get('pricelist'):
			pricelist = request.website.pricelist_id
			pricelist_context['pricelist'] = pricelist.id
		else:
			pricelist = request.env['product.pricelist'].browse(pricelist_context['pricelist'])

		return pricelist_context, pricelist



	@http.route(['/quote'], type='http', auth="public", website=True,sitemap=False)
	def quote(self,page=0, **post):
		return request.render("odoo_website_product_variant_quote.quote")

	@http.route(['/quote/cart'], type='http', auth="public", website=True,sitemap=False)
	def quote_cart(self, access_token=None, revive='', **post):
		return request.render("odoo_website_product_variant_quote.quote_cart")

	@http.route(['/quote/product/selected/<model("product.product"):product_id>'], type='http', auth="public",website=True,sitemap=False)
	def quote_multiple(self, product_id, **post):
		if post:
			quote_obj = request.env['quote.order']
			quote_line_obj = request.env['quote.order.line']
			partner = request.env.user.partner_id
			quote_order_id = request.session.get('quote_order_id')
			if not quote_order_id:
				last_quote_order = partner.last_website_quote_id
				quote_order_id = last_quote_order.id

			quote_order = request.env['quote.order'].sudo().browse(quote_order_id).exists() if quote_order_id else None

			product_product_obj = request.env['product.product'].sudo().search([('id', '=', product_id.id)], limit=1)
			request.session['quote_order_id'] = None
			if not quote_order:
				quote = quote_obj.sudo().create({'partner_id': partner.id})
				quote_line_ids = quote_line_obj.sudo().search(
					[('product_id', '=', product_id.id), ('quote_id', '=', quote.id)])

				if quote_line_ids:
					quote_line_ids.update({'qty': quote_line_ids.qty})
				else:
					quote_line = quote_line_obj.sudo().create({
						'product_id': product_product_obj.id,
						'qty': 1,
						'price': product_product_obj.lst_price,
						'quote_id': quote.id,
					})
				request.session['quote_order_id'] = quote.id
			if quote_order:
				if not request.session.get('quote_order_id'):
					request.session['quote_order_id'] = quote_order.id

				quote_line_ids = quote_line_obj.sudo().search(
					[('product_id', '=', product_id.id), ('quote_id', '=', quote_order.id)])
				if quote_line_ids:
					quote_line_ids.update({'qty': quote_line_ids.qty})
				else:
					quote_line = quote_line_obj.sudo().create({
						'product_id': product_product_obj.id,
						'qty': 1,
						'price': product_product_obj.lst_price,
						'quote_id': quote_order.id,
					})

		return request.render("odoo_website_product_variant_quote.quote_cart")

	@http.route(['/quote/product/selected/nonlogin'], type='http', auth="public", website=True,sitemap=False)
	def quote_multiple_nonlogin(self, **post):
		countries = request.env['res.country'].sudo().search([])
		states = request.env['res.country.state'].sudo().search([])
		values = {}
		values.update({
			'countries': countries,
			'states': states,
		})
		return request.render("odoo_website_product_variant_quote.get_quotation_request", values)

	@http.route(['/quote/cart/update_json'], type='json', auth="public", website=True,sitemap=False)
	def get_cart_qty(self, jsdata, **post):
		quote_cart_ids = request.env['quote.order'].sudo().browse(request.session['quote_order_id'])

		for i in quote_cart_ids.quote_lines:
			for j in jsdata:
				for x, y in j.items():

					if i.id == int(x):
						i.update({'qty': y})
		return True

	@http.route(['/process/quote'], type='http', auth="public", website=True,sitemap=False)
	def get_quote(self, **post):
		order = request.env['quote.order'].sudo().browse(request.session['quote_order_id'])
		val = {'order': order}
		return request.render("odoo_website_product_variant_quote.get_billing", val)

	@http.route(['/process/quote/nonlogin'], type='http', auth="public", website=True,sitemap=False)
	def get_quote_nonlogin(self, **post):
		if post.get('debug'):
			return request.render("odoo_website_product_variant_quote.quote_thankyou")
		if post['state_id']:
			state_id = int(post['state_id'])
		else:
			state_id = False

		partner_obj = request.env['res.partner']
		partner = partner_obj.sudo().create({
			'name': post['name'],
			'email': post['email'],
			'phone': post['phone'],
			'street': post['street'],
			'city': post['city'],
			'zip': post['zip'],
			'country_id': int(post['country_id']),
			'state_id': state_id,

		})

		order = request.env['quote.order'].sudo().browse(request.session['quote_order_id'])
		order.update({'partner_id': partner.id})
		product_obj = request.env['product.template']
		sale_order_obj = request.env['sale.order']
		sale_order_line_obj = request.env['sale.order.line']
		line_vals = {}
		pricelist_id = request.website.pricelist_id.id
		vals = {
			'partner_id': order.partner_id.id,
			'pricelist_id': pricelist_id,
			'user_id': request.website.salesperson_id and request.website.salesperson_id.id,
			'team_id': request.website.salesteam_id and request.website.salesteam_id.id
		}
		sale_order_create = sale_order_obj.sudo().create(vals)
		for i in order.quote_lines:
			line_vals = {
				'product_id': i.product_id.id,
				# 'name': sale_order_line_obj._get_sale_order_line_multiline_description_sale(),
				'product_uom_qty': i.qty,
				'customer_lead': 7,
				'product_uom': i.product_id.uom_id.id,
				'order_id': sale_order_create.id}
			sale_order_line_create = sale_order_line_obj.sudo().create(line_vals)

		order.sudo().unlink()
		request.session['quote_order_id'] = False
		return request.render("odoo_website_product_variant_quote.quote_thankyou")

	@http.route(['/shop/product/quote/confirm'], type='http', auth="public", website=True,sitemap=False)
	def quote_confirm(self, **post):
		order = request.env['quote.order'].sudo().browse(request.session['quote_order_id'])
		if order:
			product_obj = request.env['product.template']
			partner_obj = request.env['res.partner']
			sale_order_obj = request.env['sale.order']
			sale_order_line_obj = request.env['sale.order.line']
			line_vals = {}
			pricelist_id = request.website.pricelist_id.id
			vals = {
				'partner_id': order.partner_id.id,
				'pricelist_id': pricelist_id,
				'user_id': request.website.salesperson_id and request.website.salesperson_id.id,
				'team_id': request.website.salesteam_id and request.website.salesteam_id.id
			}
			sale_order_create = sale_order_obj.sudo().create(vals)
			for i in order.quote_lines:
				line_vals = {
					'product_id': i.product_id.id,
					# 'name': sale_order_line_obj._get_sale_order_line_multiline_description_sale(),
					'product_uom_qty': i.qty,
					'customer_lead': 7,
					'product_uom': i.product_id.uom_id.id,
					'order_id': sale_order_create.id}
				sale_order_line_create = sale_order_line_obj.sudo().create(line_vals)
			order.sudo().unlink()
			request.session['quote_order_id'] = False
		return request.render("odoo_website_product_variant_quote.quote_thankyou")

	@http.route(['/quote/delete/<model("quote.order.line"):line>'], type='http', auth="public", website=True,sitemap=False)
	def qoute_delete(self, **post):
		order = post['line']
		order.sudo().unlink()
		return request.render("odoo_website_product_variant_quote.quote_cart")

	@http.route(['/thank_you'], type='http', auth="public", website=True,sitemap=False)
	def thank_you(self, **post):
		return request.render("odoo_website_product_variant_quote.quote_thankyou")
