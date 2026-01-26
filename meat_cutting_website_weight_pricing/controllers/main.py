# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import UserError

from odoo.addons.website_sale.controllers.main import WebsiteSale

class WebsiteSaleMC(WebsiteSale):

    @http.route(['/shop/payment'], type='http', auth="public", website=True, sitemap=False)
    def shop_payment(self, **post):
        order = request.website.sale_get_order()
        if order and order.state in ("draft", "sent"):
            try:
                order.sudo().mc_web_reserve_and_recompute()
            except UserError as e:
                # mostrar mensaje y regresar al carrito (bloqueo de checkout)
                request.session['mc_web_weight_error'] = str(e)
                return request.redirect('/shop/cart')
        return super().shop_payment(**post)

    @http.route(['/shop/cart'], type='http', auth="public", website=True, sitemap=False)
    def cart(self, access_token=None, revive='', **post):
        resp = super().cart(access_token=access_token, revive=revive, **post)
        msg = request.session.pop('mc_web_weight_error', None)
        if msg:
            # inyectar warning en el render (si es template response)
            try:
                if hasattr(resp, 'qcontext'):
                    resp.qcontext['mc_web_weight_error'] = msg
            except Exception:
                pass
        return resp
