
# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class WholesaleHomeController(http.Controller):
    @http.route(['/home-mayoreo', '/home-mayoreo/'], type='http', auth='public', website=True, sitemap=True)
    def wholesale_home(self, **kwargs):
        path = request.httprequest.path
        page = request.env['website.page'].sudo().search([
            ('url', 'in', ['/home-mayoreo', '/home-mayoreo/']),
            ('website_id', 'in', [False, request.website.id]),
        ], limit=1, order='website_id desc')

        if not page:
            return request.not_found()

        view = page.view_id.sudo() if page.view_id else None
        if view and getattr(view, 'visibility', False) == 'invitation':
            if request.env.user._is_public():
                return request.redirect('/web/login?redirect=%s' % path)

            p = request.env.user.partner_id.sudo()
            allowed = bool(
                getattr(p, 'is_wholesale_access', False) or
                (p.parent_id and getattr(p.parent_id, 'is_wholesale_access', False)) or
                (p.commercial_partner_id and getattr(p.commercial_partner_id, 'is_wholesale_access', False))
            )
            if not allowed:
                return http.Response('403 Forbidden', status=403)

        key = (page.view_id and page.view_id.key) or page.key
        if key:
            return request.render(key, {})
        return request.not_found()
