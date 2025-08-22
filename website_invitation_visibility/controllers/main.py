
# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import Website

def _has_wholesale_access(partner):
    return bool(partner and getattr(partner, 'is_wholesale_access', False))

class WebsiteInvitation(Website):
    @http.route(['/page/<path:page>', '/<path:page>'], type='http', auth="public", website=True, sitemap=True)
    def page(self, page=None, **opt):
        req_path = request.httprequest.path  # e.g. '/home-mayoreo'
        # Build candidate URLs that may be stored on website.page.url
        candidates = set()
        if req_path:
            candidates.add(req_path)
            candidates.add(req_path.rstrip('/'))
            candidates.add(req_path.rstrip('/') + '/')
            if req_path.startswith('/page/'):
                candidates.add('/' + req_path.split('/page/', 1)[1])
            else:
                candidates.add('/page' + req_path)
        if page:
            candidates.add('/' + page.lstrip('/'))
            candidates.add('/page/' + page.lstrip('/'))
        # Search page on current website (or global)
        domain = [('url', 'in', list(candidates)), ('website_id', 'in', [False, request.website.id])]
        page_rec = request.env['website.page'].sudo().search(domain, limit=1, order='website_id desc')
        if page_rec:
            view = page_rec.view_id.sudo() if page_rec.view_id else None
            if view and getattr(view, 'visibility', False) == 'invitation':
                if request.env.user._is_public():
                    return request.redirect('/web/login?redirect=%s' % req_path)
                partner = request.env.user.partner_id.sudo()
                if not _has_wholesale_access(partner):
                    return request.render('website_invitation_visibility.invitation_denied_template', {
                        'page': page_rec,
                        'tag_name': 'Acceso Mayoristas',
                    })
                # Authorized: render the page template directly
                key = (page_rec.key or (page_rec.view_id and page_rec.view_id.key))
                if key:
                    return request.render(key, {})
        # Default
        return super(WebsiteInvitation, self).page(page, **opt)
