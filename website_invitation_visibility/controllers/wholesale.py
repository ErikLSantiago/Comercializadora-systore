
# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class WholesaleHomeController(http.Controller):
    @http.route(['/home-mayoreo', '/home-mayoreo/'], type='http', auth='public', website=True, sitemap=True)
    def wholesale_home(self, **kwargs):
        path = request.httprequest.path
        # Find the website.page for this route on current website (or global)
        page = request.env['website.page'].sudo().search([
            ('url', 'in', ['/home-mayoreo', '/home-mayoreo/']),
            ('website_id', 'in', [False, request.website.id]),
        ], limit=1, order='website_id desc')

        if not page:
            return request.not_found()

        view = page.view_id.sudo() if page.view_id else None
        if view and getattr(view, 'visibility', False) == 'invitation':
            # Require login
            if request.env.user._is_public():
                return request.redirect('/web/login?redirect=%s' % path)

            # Check partner/company flag
            p = request.env.user.partner_id.sudo()
            allowed = bool(
                getattr(p, 'is_wholesale_access', False) or
                (p.parent_id and getattr(p.parent_id, 'is_wholesale_access', False)) or
                (p.commercial_partner_id and getattr(p.commercial_partner_id, 'is_wholesale_access', False))
            )
            if not allowed:
                # Use core website 403 page
                return request.render('website.403')

        # Authorized or not invitation -> render the page
        key = page.key or (page.view_id and page.view_id.key)
        if key:
            return request.render(key, {})
        return request.not_found()
