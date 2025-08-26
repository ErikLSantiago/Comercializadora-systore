# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class WebsiteQuoteRequest(http.Controller):

    def _get_partner_for_order(self):
        user = request.env.user
        if user._is_public():
            website = request.website
            if website and website.user_id and website.user_id.partner_id:
                return website.user_id.partner_id.sudo()
            return request.env.ref('base.public_partner', raise_if_not_found=False).sudo()
        return user.partner_id.sudo()

    def _get_pricelist(self):
        website = request.website
        if website and website.pricelist_id:
            return website.pricelist_id.sudo()
        return request.env['product.pricelist'].sudo().search([], limit=1)

    def _get_or_create_order(self):
        Order = request.env['sale.order'].sudo()
        order = None
        so_id = request.session.get('wqr_order_id')
        if so_id:
            order = Order.browse(int(so_id))
            if not order.exists():
                order = None
        if not order:
            partner = self._get_partner_for_order()
            pricelist = self._get_pricelist()
            order = Order.create({
                'partner_id': partner.id if partner else False,
                'pricelist_id': pricelist.id if pricelist else False,
                'wqr_is_request': True,
            })
            request.session['wqr_order_id'] = order.id
        return order

    def _collect_facets(self, products):
        # Build website public categories (product.public.category) and attribute value facets from given templates
        # Aggregate all public categories used by the given products
        pub_cats = request.env['product.public.category'].sudo()
        for t in products:
            pub_cats |= t.public_categ_ids
        categories = pub_cats
        # attribute values present
        attr_values = request.env['product.attribute.value'].sudo()
        for t in products:
            for line in t.attribute_line_ids:
                attr_values |= line.value_ids
        # group by attribute
        attrs = {}
        for v in attr_values:
            attrs.setdefault(v.attribute_id, request.env['product.attribute.value'].sudo())
            attrs[v.attribute_id] |= v
        # Convert to list of dicts for template
        attr_buckets = []
        for attr, vals in attrs.items():
            attr_buckets.append({
                'id': attr.id,
                'name': attr.name,
                'values': [{'id': v.id, 'name': v.name} for v in vals.sorted(key=lambda r: r.sequence)],
            })
        attr_buckets.sort(key=lambda a: a['name'].lower())
        cat_list = [{'id': c.id, 'name': getattr(c, 'complete_name', c.display_name)} for c in categories.sorted(key=lambda r: getattr(r, 'complete_name', r.display_name))]
        return cat_list, attr_buckets

    def _filter_products(self, base_domain, kw):
        env = request.env
        T = env['product.template'].sudo()
        products = T.search(base_domain, order="name asc")

        # parse filters
        search = (kw.get('search') or '').strip()
        cat = int(kw.get('cat', 0) or 0)

        # Selected attribute values: we use checkbox names "av_<id>=on"
        selected_av = []
        for k, v in kw.items():
            if k.startswith('av_') and v:
                try:
                    selected_av.append(int(k.split('_', 1)[1]))
                except Exception:
                    pass

        # Apply search
        if search:
            products = products.filtered(lambda p: (search.lower() in (p.name or '').lower()) or (search.lower() in (p.default_code or '').lower()))

        # Apply website public category
        if cat:
            products = products.filtered(lambda p: p.public_categ_ids and (cat in p.public_categ_ids.ids))

        # Apply attribute values (must match ALL selected)
        if selected_av:
            sel_set = set(selected_av)
            def tmpl_has_all_values(tmpl):
                tvals = set()
                for line in tmpl.attribute_line_ids:
                    for v in line.value_ids:
                        tvals.add(v.id)
                return sel_set.issubset(tvals)
            products = products.filtered(lambda p: tmpl_has_all_values(p))

        return products, {'search': search, 'cat': cat, 'selected_av': selected_av}

    @http.route(['/quote'], type='http', auth='public', website=True, sitemap=True)
    def quote_page(self, **kw):
        base_domain = [('quote_publish','=',True)]
        products, state = self._filter_products(base_domain, kw)

        # Current order context: added badges and qty memory
        so_id = request.session.get('wqr_order_id')
        added_ids = set()
        template_qtys = {}
        if so_id:
            order = request.env['sale.order'].sudo().browse(int(so_id))
            if order.exists():
                for l in order.order_line:
                    tmpl_id = l.product_id.product_tmpl_id.id
                    added_ids.add(tmpl_id)
                    template_qtys[tmpl_id] = template_qtys.get(tmpl_id, 0) + l.product_uom_qty

        # Build facets from all published (unfiltered) products to avoid disappearing options
        all_published = request.env['product.template'].sudo().search(base_domain)
        categories, attr_buckets = self._collect_facets(all_published)

        return request.render('website_quote_request.quote_page', {
            'products': products,
            'added_ids': added_ids,
            'template_qtys': template_qtys,
            'facets_categories': categories,
            'facets_attributes': attr_buckets,
            'state': state,
        })

    @http.route(['/quote/add'], type='http', auth='public', methods=['POST'], website=True, csrf=True)
    def quote_add(self, product_id=None, qty=None, **post):
        try:
            product_id = int(product_id or 0)
            qty = float(qty or 1.0)
        except Exception:
            product_id, qty = 0, 1.0
        if product_id <= 0 or qty <= 0:
            return request.redirect('/quote')
        order = self._get_or_create_order()
        product = request.env['product.product'].sudo().search([('product_tmpl_id','=',product_id)], limit=1)
        if not product:
            return request.redirect('/quote')
        existing = order.order_line.filtered(lambda l: l.product_id.product_tmpl_id.id == product.product_tmpl_id.id)[:1]
        if existing:
            existing.sudo().write({'product_uom_qty': existing.product_uom_qty + qty})
        else:
            request.env['sale.order.line'].sudo().create({
                'order_id': order.id,
                'product_id': product.id,
                'name': product.display_name,
                'product_uom_qty': qty,
                'product_uom': product.uom_id.id,
                'price_unit': 0.0,
            })
        return request.redirect('/quote')

    @http.route(['/quote/cart'], type='http', auth='public', website=True, sitemap=False)
    def quote_cart(self, **kw):
        so_id = request.session.get('wqr_order_id')
        order = None
        total_qty = 0
        if so_id:
            order = request.env['sale.order'].sudo().browse(int(so_id))
            if order.exists():
                total_qty = sum(order.order_line.mapped('product_uom_qty'))
            else:
                order = None
        return request.render('website_quote_request.quote_cart', {
            'order': order,
            'total_qty': int(total_qty),
        })

    @http.route(['/quote/update'], type='http', auth='public', methods=['POST'], website=True, csrf=True)
    def quote_update(self, line_id=None, qty=None, **post):
        try:
            line = request.env['sale.order.line'].sudo().browse(int(line_id))
            if line.exists():
                q = float(qty or 1.0)
                if q <= 0:
                    line.unlink()
                else:
                    line.write({'product_uom_qty': q})
        except Exception:
            pass
        return request.redirect('/quote/cart')

    @http.route(['/quote/submit'], type='http', auth='public', methods=['POST'], website=True, csrf=True)
    def quote_submit(self, **post):
        so_id = request.session.get('wqr_order_id')
        if not so_id:
            return request.redirect('/quote')
        order = request.env['sale.order'].sudo().browse(int(so_id))
        if not order.exists() or not order.order_line:
            return request.redirect('/quote')
        order.sudo().write({'wqr_submitted': True})
        comments = (post.get('comments') or '').strip()
        body = "Solicitud de cotización enviada desde el sitio web." + ("<br/><br/><b>Comentarios del cliente:</b><br/>%s" % request.env['ir.qweb.field.html']._sanitize_html(comments) if comments else '')
        order.message_post(body=body)
        # Keep order in context for thanks page but clear session for a new cycle
        request.session.pop('wqr_order_id', None)
        return request.render('website_quote_request.quote_thanks', {'order': order})
