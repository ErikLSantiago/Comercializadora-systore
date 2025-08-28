
from odoo import http, _
from odoo.http import request
from odoo.tools import html_sanitize

SESSION_KEY = 'wqr_cart'
LAST_ORDER_NAME_KEY = 'wqr_last_order_name'

def _get_cart():
    cart = request.session.get(SESSION_KEY)
    if not isinstance(cart, dict):
        cart = {}
    return {int(k): int(v) for k, v in cart.items()} if cart else {}

def _set_cart(cart):
    request.session[SESSION_KEY] = {int(k): int(v) for k, v in cart.items()}
    request.session.modified = True

def _ensure_positive_int(val, default=1):
    try:
        v = int(val)
        return v if v > 0 else default
    except Exception:
        return default

def _has_partner_access():
    user = request.env.user
    if user and not user._is_public():
        partner = user.partner_id.sudo()
        return bool(partner and partner.wqr_quote_access)
    return False

class WebsiteQuoteRequest(http.Controller):

    def _guard_or_render(self, template, values):
        if not _has_partner_access():
            return request.render('website_quote_request.quote_no_access', {})
        return request.render(template, values)

    @http.route(['/quote'], type='http', auth='public', website=True, sitemap=True)
    def quote_list(self, **kwargs):
        env = request.env
        Product = env['product.template'].sudo()
        PubCat = env['product.public.category'].sudo()
        PAV = env['product.attribute.value'].sudo()

        args = request.httprequest.args
        q = (args.get('q') or '').strip()
        c_list = args.getlist('c') or []
        av_list = args.getlist('av') or []

        def _to_ids(raw_list):
            ids = []
            for v in raw_list:
                if not v:
                    continue
                for tok in str(v).split(','):
                    tok = tok.strip()
                    if tok.isdigit():
                        ids.append(int(tok))
            return ids

        selected_cat_ids = _to_ids(c_list)
        selected_av_ids = _to_ids(av_list)

        domain = [('quote_publish', '=', True)]
        if q:
            domain += ['|', ('name', 'ilike', q), ('product_variant_ids.default_code', 'ilike', q)]
        if selected_cat_ids:
            domain.append(('public_categ_ids', 'in', selected_cat_ids))
        if selected_av_ids:
            domain.append(('attribute_line_ids.value_ids', 'in', selected_av_ids))

        products = Product.search(domain, order='name asc', limit=36)
        facet_products = Product.search(domain, order='name asc', limit=500)

        cat_ids = set()
        for p in facet_products:
            cat_ids.update(p.public_categ_ids.ids)
        categories = PubCat.browse(list(cat_ids)).sorted(key=lambda c: (c.sequence, (c.name or '').lower()))

        av_ids = set()
        for p in facet_products:
            for al in p.attribute_line_ids:
                av_ids.update(al.value_ids.ids)
        av_records = PAV.browse(list(av_ids))
        groups = {}
        for v in av_records:
            groups.setdefault(v.attribute_id, []).append(v)
        def _attr_key(attr):
            nm = (attr.name or '').lower()
            return (0 if nm in ('marca','brand') else 1, nm)
        grouped_attrs = sorted(groups.items(), key=lambda it: _attr_key(it[0]))
        for attr, vals in grouped_attrs:
            vals.sort(key=lambda x: (x.attribute_id.sequence, x.sequence, (x.name or '').lower()))

        primary_attr = None
        primary_vals = []
        other_attr_groups = []
        if grouped_attrs:
            primary_attr, primary_vals = grouped_attrs[0]
            other_attr_groups = grouped_attrs[1:]

        cart = _get_cart()
        cart_count = sum(cart.values())

        values = {
            'products': products,
            'categories': categories,
            'selected_cat_ids': selected_cat_ids,
            'primary_attr': primary_attr,
            'primary_vals': primary_vals,
            'other_attr_groups': other_attr_groups,
            'selected_av_ids': selected_av_ids,
            'q': q,
            'cart': cart,
            'cart_count': cart_count,
        }
        return self._guard_or_render('website_quote_request.quote_list', values)

    @http.route(['/quote/add'], type='http', auth='public', methods=['POST'], website=True, csrf=True)
    def quote_add(self, **post):
        if not _has_partner_access():
            return request.render('website_quote_request.quote_no_access', {})
        product_id = int(post.get('product_id', 0) or 0)
        qty = _ensure_positive_int(post.get('qty', 1), 1)
        if product_id:
            cart = _get_cart()
            cart[product_id] = cart.get(product_id, 0) + qty
            _set_cart(cart)
        return request.redirect('/quote')

    @http.route(['/quote/cart'], type='http', auth='public', website=True, sitemap=False)
    def quote_cart(self, **kwargs):
        if not _has_partner_access():
            return request.render('website_quote_request.quote_no_access', {})
        env = request.env
        Product = env['product.template'].sudo()
        cart = _get_cart()

        items, total_qty = [], 0
        product_ids = list(cart.keys())
        products = Product.browse(product_ids)
        for p in products:
            q = cart.get(p.id, 0)
            items.append({'product': p, 'qty': q})
            total_qty += q

        return request.render('website_quote_request.quote_cart', {
            'items': items,
            'total_qty': total_qty,
            'prefill': {
                'name': request.env.user.name if request.env.user and not request.env.user._is_public() else '',
                'email': request.env.user.email if request.env.user and not request.env.user._is_public() else '',
                'phone': request.env.user.phone if request.env.user and not request.env.user._is_public() else '',
            }
        })

    @http.route(['/quote/update'], type='http', auth='public', methods=['POST'], website=True, csrf=True)
    def quote_update(self, **post):
        if not _has_partner_access():
            return request.render('website_quote_request.quote_no_access', {})
        cart = _get_cart()
        for key, val in post.items():
            if key.startswith('qty_'):
                pid = int(key[4:])
                qty = _ensure_positive_int(val, 0)
                if qty > 0:
                    cart[pid] = qty
                else:
                    cart.pop(pid, None)
        _set_cart(cart)
        return request.redirect('/quote/cart')

    @http.route(['/quote/submit'], type='http', auth='public', methods=['POST'], website=True, csrf=True)
    def quote_submit(self, **post):
        if not _has_partner_access():
            return request.render('website_quote_request.quote_no_access', {})
        env = request.env
        cart = _get_cart()
        Product = env['product.template'].sudo()
        if not cart:
            return request.redirect('/quote')

        name = (post.get('name') or '').strip()
        email = (post.get('email') or '').strip()
        phone = (post.get('phone') or '').strip()
        comments = (post.get('comments') or '').strip()

        if request.env.user and not request.env.user._is_public():
            partner = request.env.user.partner_id.sudo()
        else:
            Partner = env['res.partner'].sudo()
            partner = False
            if email:
                partner = Partner.search([('email', '=', email)], limit=1)
            if not partner:
                partner = Partner.create({'name': name or _('Cliente Website'), 'email': email or False, 'phone': phone or False})

        order = env['sale.order'].sudo().create({'partner_id': partner.id, 'origin': 'Website Quote Request'})

        SOL = env['sale.order.line'].sudo()
        total_pieces = 0
        products = Product.browse(list(cart.keys()))
        for p in products:
            qty = int(cart.get(p.id) or 0)
            if qty <= 0:
                continue
            total_pieces += qty
            product_product = p.product_variant_id
            SOL.create({
                'order_id': order.id,
                'product_id': product_product.id,
                'product_uom_qty': qty,
                'price_unit': product_product.lst_price,
                'name': p.name,
            })

        order.wqr_total_pieces = total_pieces

        body = _("Solicitud de cotización enviada desde el sitio web.")
        if comments:
            body += "<br/><br/><b>%s</b><br/>%s" % (_('Comentarios del cliente:'), html_sanitize(comments))
        order.message_post(body=body)

        request.session[LAST_ORDER_NAME_KEY] = order.name
        _set_cart({})

        return request.redirect('/quote/thanks?o=%s' % (order.name or ''))

    @http.route(['/quote/thanks'], type='http', auth='public', website=True, sitemap=False)
    def quote_thanks(self, **kwargs):
        if not _has_partner_access():
            return request.render('website_quote_request.quote_no_access', {})
        order_name = request.httprequest.args.get('o') or request.session.get(LAST_ORDER_NAME_KEY) or ''
        if request.session.get(LAST_ORDER_NAME_KEY):
            request.session.pop(LAST_ORDER_NAME_KEY, None)
            request.session.modified = True
        return request.render('website_quote_request.quote_thanks', {'order_name': order_name})
