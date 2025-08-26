
from odoo import http, _
from odoo.http import request
from odoo.tools import html_sanitize

class WebsiteQuoteRequest(http.Controller):

    @http.route(['/quote'], type='http', auth='public', website=True, sitemap=True)
    def quote_form(self, **kwargs):
        return request.render('website_quote_request.quote_form', {})

    @http.route(['/quote/submit'], type='http', auth="public", website=True, csrf=True)
    def quote_submit(self, **post):
        comments = (post.get('comments') or '').strip()
        # partner: logged partner or placeholder
        partner = request.env.user.partner_id.sudo() if request.env.user and not request.env.user._is_public() else request.env['res.partner'].sudo().create({'name': _('Cliente Website')})
        order = request.env['sale.order'].sudo().create({'partner_id': partner.id})
        safe_comments = html_sanitize(comments) if comments else ''
        body = _("Solicitud de cotización enviada desde el sitio web.")
        if safe_comments:
            body += "<br/><br/><b>%s</b><br/>%s" % (_('Comentarios del cliente:'), safe_comments)
        order.message_post(body=body)
        return request.redirect('/quote/thanks')

    @http.route(['/quote/thanks'], type='http', auth='public', website=True, sitemap=False)
    def quote_thanks(self, **kwargs):
        return request.render('website_quote_request.quote_thanks', {})
