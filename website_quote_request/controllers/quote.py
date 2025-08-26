
from odoo import http, _
from odoo.http import request
from odoo.tools import html_sanitize

SESSION_KEY = 'wqr_cart'  # product_id -> qty

def _get_cart():
    return request.session.get(SESSION_KEY, {})

def _set_cart(cart):
    request.session[SESSION_KEY] = cart
    request.session.modified = True

def _ensure_positive_int(val, default=1):
    try:
        v = int(val)
        return v if v > 0 else default
    except Exception:
        return default

class WebsiteQuoteRequest(http.Controller):

    # Listado de productos con filtro por categorias publicas
    @http.route(['/quote'], type='http', auth='public', website=True, sitemap=True)
    def quote_list(self, **kwargs):
        env = request.env
        Product = env['product.template'].sudo()
        PubCat = env['product.public.category'].sudo()

        # Filtro por categoría pública (param 'c')
        c = kwargs.get('c')
        domain = [('website_published', '=', True)]
        selected_cat = False
        if c:
            try:
                c_id = int(c)
                selected_cat = PubCat.browse(c_id)
                if selected_cat and selected_cat.exists():
                    domain.append(('public_categ_ids', 'in', [c_id]))
            except Exception:
                pass

        products = Product.search(domain, limit=24, order='name asc')

        # Categorías para el facet (todas publicadas)
        categories = PubCat.search([], order='sequence, name')

        # Carrito actual
        cart = _get_cart()
        cart_count = sum(cart.values())

        values = {
            'products': products,
            'categories': categories,
            'selected_cat': selected_cat,
            'cart': cart,
            'cart_count': cart_count,
        }
        return request.render('website_quote_request.quote_list', values)

    # Agregar producto al carrito de cotizacion
    @http.route(['/quote/add'], type='http', auth='public', methods=['POST'], website=True, csrf=True)
    def quote_add(self, **post):
        product_id = int(post.get('product_id', 0) or 0)
        qty = _ensure_positive_int(post.get('qty', 1), 1)
        if product_id:
            cart = _get_cart()
            cart[str(product_id)] = cart.get(str(product_id), 0) + qty
            _set_cart(cart)
        return request.redirect('/quote')

    # Ver carrito / ver solicitud
    @http.route(['/quote/cart'], type='http', auth='public', website=True, sitemap=False)
    def quote_cart(self, **kwargs):
        env = request.env
        Product = env['product.template'].sudo()
        cart = _get_cart()

        items = []
        total_qty = 0
        product_ids = [int(pid) for pid in cart.keys()]
        products = Product.browse(product_ids)
        for p in products:
            q = cart.get(str(p.id), 0)
            items.append({'product': p, 'qty': q})
            total_qty += q

        values = {
            'items': items,
            'total_qty': total_qty,
            'prefill': {
                'name': request.env.user.name if request.env.user and not request.env.user._is_public() else '',
                'email': request.env.user.email if request.env.user and not request.env.user._is_public() else '',
                'phone': request.env.user.phone if request.env.user and not request.env.user._is_public() else '',
            }
        }
        return request.render('website_quote_request.quote_cart', values)

    # Actualizar cantidades en el carrito
    @http.route(['/quote/update'], type='http', auth='public', methods=['POST'], website=True, csrf=True)
    def quote_update(self, **post):
        cart = _get_cart()
        # post keys like qty_<product_id>
        for key, val in post.items():
            if key.startswith('qty_'):
                pid = key[4:]
                qty = _ensure_positive_int(val, 0)
                if qty > 0:
                    cart[pid] = qty
                else:
                    cart.pop(pid, None)
        _set_cart(cart)
        return request.redirect('/quote/cart')

    # Enviar cotizacion -> crear sale.order con lineas
    @http.route(['/quote/submit'], type='http', auth='public', methods=['POST'], website=True, csrf=True)
    def quote_submit(self, **post):
        env = request.env
        cart = _get_cart()
        Product = env['product.template'].sudo()

        if not cart:
            return request.redirect('/quote')

        # Datos de contacto
        name = (post.get('name') or '').strip()
        email = (post.get('email') or '').strip()
        phone = (post.get('phone') or '').strip()
        comments = (post.get('comments') or '').strip()

        # Partner
        if request.env.user and not request.env.user._is_public():
            partner = request.env.user.partner_id.sudo()
        else:
            # Si no está logueado, crear/usar partner por email o nombre
            Partner = env['res.partner'].sudo()
            partner = False
            if email:
                partner = Partner.search([('email', '=', email)], limit=1)
            if not partner:
                partner = Partner.create({'name': name or _('Cliente Website'), 'email': email or False, 'phone': phone or False})

        # Crear orden
        Order = env['sale.order'].sudo()
        order_vals = {
            'partner_id': partner.id,
            'origin': 'Website Quote Request',
        }
        order = Order.create(order_vals)

        # Agregar lineas por cada product.template del carrito (usar product_variant_id)
        SOL = env['sale.order.line'].sudo()
        product_ids = [int(pid) for pid in cart.keys()]
        products = Product.browse(product_ids)
        for p in products:
            qty = int(cart.get(str(p.id)) or 0)
            if qty <= 0:
                continue
            product_product = p.product_variant_id
            SOL.create({
                'order_id': order.id,
                'product_id': product_product.id,
                'product_uom_qty': qty,
                'price_unit': product_product.lst_price,
                'name': p.name,
            })

        # Publicar comentarios sanitizados
        if comments:
            safe_comments = html_sanitize(comments)
            body = _("Solicitud de cotización enviada desde el sitio web.")
            body += "<br/><br/><b>%s</b><br/>%s" % (_('Comentarios del cliente:'), safe_comments)
        else:
            body = _("Solicitud de cotización enviada desde el sitio web.")
        order.message_post(body=body)

        # Vaciar carrito de sesión
        _set_cart({})

        return request.redirect('/quote/thanks')

    # Gracias
    @http.route(['/quote/thanks'], type='http', auth='public', website=True, sitemap=False)
    def quote_thanks(self, **kwargs):
        return request.render('website_quote_request.quote_thanks', {})
