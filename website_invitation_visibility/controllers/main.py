
# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import Website

class WebsiteInvitation(Website):
    @http.route(['/page/<path:page>', '/<path:page>'], type='http', auth="public", website=True, sitemap=True)
    def page(self, page=None, **opt):
        # If the target is a website.page with our custom visibility and the user is public,
        # send them to login. For all other cases, let the core handle visibility (we override _is_visible).
        req_path = request.httprequest.path
        page_rec = request.env['website.page'].sudo().search(
            [('url', 'in', [req_path, req_path.rstrip('/'), req_path.rstrip('/') + '/'])],
            limit=1
        )
        if page_rec and page_rec.view_id and getattr(page_rec.view_id, 'visibility', False) == 'invitation':
            if request.env.user._is_public():
                return request.redirect('/web/login?redirect=%s' % req_path)
        return super(WebsiteInvitation, self).page(page, **opt)
