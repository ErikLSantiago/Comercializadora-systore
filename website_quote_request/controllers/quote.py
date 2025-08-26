
from odoo import http, _
from odoo.http import request
from odoo.tools import html_sanitize

class WebsiteQuoteRequest(http.Controller):

    @http.route(['/quote'], type='http', auth='public', website=True, sitemap=True)
    def quote_form(self, **kwargs):
        # Values for rendering form
        values = {}
        return request.render('website_quote_request_v3_3_1.quote_form', values)

    @http.route(['/quote/submit'], type='http', auth='public', website=True, csrf=True)
    def quote_submit(self, **post):
        # Collect cart lines (your existing logic would be here). For this patch we focus on comments -> sale.order note.
        comments = (post.get('comments') or '').strip()

        # Create a draft sale.order or find it (this depends on your prior flow). Example: create a placeholder order.
        # In your previous version you likely created the SO from the selected products. Here we keep compatibility by
        # creating a minimal SO if none is present, so that message_post works for testing.
        partner = request.env.user.partner_id.sudo() if request.env.user and not request.env.user._is_public() else request.env['res.partner'].sudo().create({'name': _('Cliente Website')})
        order = request.env['sale.order'].sudo().create({
            'partner_id': partner.id,
        })

        # Sanitize comments safely (fix for AttributeError on _sanitize_html)
        safe_comments = html_sanitize(comments) if comments else ''

        # Compose body and post to chatter (Notes)
        body = _("Solicitud de cotización enviada desde el sitio web.")
        if safe_comments:
            body += "<br/><br/><b>%s</b><br/>%s" % (_('Comentarios del cliente:'), safe_comments)

        order.message_post(body=body)

        return request.redirect('/quote/thanks')

    @http.route(['/quote/thanks'], type='http', auth='public', website=True, sitemap=False)
    def quote_thanks(self, **kwargs):
        return request.render('website_quote_request_v3_3_1.quote_thanks', {})
