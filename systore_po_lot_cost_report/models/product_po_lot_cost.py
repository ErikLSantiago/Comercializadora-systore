# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProductPoLotCostLine(models.Model):
    _name = "product.po.lot.cost.line"
    _description = "Costo operativo por Lote / Orden de Compra"
    _order = "date_order desc, purchase_order_id desc, lot_id, product_id"

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)

    product_tmpl_id = fields.Many2one("product.template", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one("product.product", required=True, ondelete="cascade", index=True)

    lot_id = fields.Many2one("stock.lot", string="Lote", index=True)
    location_id = fields.Many2one('stock.location', string='Ubicación', readonly=True, index=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Almacén', readonly=True, index=True)

    purchase_order_id = fields.Many2one("purchase.order", string="Orden de compra", index=True)
    purchase_order_line_id = fields.Many2one("purchase.order.line", string="Línea OC", index=True)
    vendor_id = fields.Many2one("res.partner", string="Proveedor", index=True)
    date_order = fields.Datetime(string="Fecha OC", index=True)

    qty_available = fields.Float(string="Cantidad disponible", digits="Product Unit of Measure")
    reserved_qty = fields.Float(string="Reservadas", digits="Product Unit of Measure", readonly=True)
    uom_id = fields.Many2one("uom.uom", string="UdM", readonly=True)

    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)
    price_unit = fields.Monetary(string="Costo OC (actual)", currency_field="currency_id")
    value_subtotal = fields.Monetary(
        string="Valor real (operativo)",
        currency_field="currency_id",
        compute="_compute_value_subtotal",
        store=False,
    )

    note = fields.Char(string="Nota")

    @api.depends("qty_available", "price_unit")
    def _compute_value_subtotal(self):
        for rec in self:
            rec.value_subtotal = (rec.qty_available or 0.0) * (rec.price_unit or 0.0)




class ProductPoLotCostWarehouseSummary(models.Model):
    _name = "product.po.lot.cost.wh.summary"
    _description = "Resumen de costo por almacén (operativo)"
    _order = "warehouse_id"

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    product_tmpl_id = fields.Many2one("product.template", required=True, ondelete="cascade", index=True)

    warehouse_id = fields.Many2one("stock.warehouse", string="Almacén", index=True)
    warehouse_name = fields.Char(string="Almacén", readonly=True)
    reserved_total = fields.Float(string="Reservadas", digits="Product Unit of Measure")
    qty_total = fields.Float(string="Total piezas", digits="Product Unit of Measure")
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)
    value_total = fields.Monetary(string="Valor total", currency_field="currency_id")
    avg_cost = fields.Monetary(string="Costo promedio", currency_field="currency_id",
                               compute="_compute_avg_cost", store=False)

    @api.depends("qty_total", "value_total")
    def _compute_avg_cost(self):
        for rec in self:
            rec.avg_cost = (rec.value_total / rec.qty_total) if rec.qty_total else 0.0


class ProductTemplate(models.Model):
    _inherit = "product.template"

    company_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda compañía",
        related="company_id.currency_id",
        readonly=True,
    )

    po_lot_cost_wh_summary_ids = fields.One2many(
        'product.po.lot.cost.wh.summary',
        'product_tmpl_id',
        string='Resumen por almacén',
        readonly=True,
    )

    po_lot_cost_line_ids = fields.One2many(
        "product.po.lot.cost.line",
        "product_tmpl_id",
        string="Costos por Lote/OC",
        readonly=True,
    )

    po_lot_cost_qty_total = fields.Float(
        string="Total cantidad (reporte)",
        compute="_compute_po_lot_cost_totals",
        store=False,
        digits="Product Unit of Measure",
    )
    po_lot_cost_value_total = fields.Monetary(
        string="Total valor real (reporte)",
        compute="_compute_po_lot_cost_totals",
        store=False,
        currency_field="company_currency_id",
    )

    @api.depends("po_lot_cost_line_ids.qty_available", "po_lot_cost_line_ids.price_unit", "po_lot_cost_line_ids.currency_id")
    def _compute_po_lot_cost_totals(self):
        company_currency = self.env.company.currency_id
        today = fields.Date.today()
        for tmpl in self:
            qty_total = 0.0
            value_total_company = 0.0
            for line in tmpl.po_lot_cost_line_ids:
                qty_total += line.qty_available or 0.0
                amount = (line.qty_available or 0.0) * (line.price_unit or 0.0)
                if line.currency_id and line.currency_id != company_currency:
                    amount = line.currency_id._convert(amount, company_currency, tmpl.company_id, today)
                value_total_company += amount
            tmpl.po_lot_cost_qty_total = qty_total
            tmpl.po_lot_cost_value_total = value_total_company

    def _get_warehouse_from_location(self, location, company, Warehouse=None, cache=None):
        """Return stock.warehouse for a given stock.location.

        We keep a local cache dict because Odoo recordsets cannot be assigned arbitrary
        attributes (no __dict__). Cache key: (company_id, location_id).
        """
        Warehouse = Warehouse or self.env['stock.warehouse'].sudo()
        if not location:
            return False

        cache = cache or {}
        key = ((company.id if company else False), location.id)
        if key in cache:
            return cache[key]

        loc = location.sudo()

        # Walk up the location hierarchy and try to match a warehouse view_location_id
        wh = False
        cur = loc
        while cur and cur.location_id:
            # view_location_id is the "root" location of a warehouse
            wh = Warehouse.search([
                ('company_id', '=', company.id) if company else ('id', '!=', 0),
                ('view_location_id', '=', cur.id),
            ], limit=1)
            if wh:
                break
            cur = cur.location_id

        # If not found, fallback: check if the original location is within a warehouse view location
        if not wh:
            domain = [('view_location_id', 'child_of', loc.id)]
            if company:
                domain.insert(0, ('company_id', '=', company.id))
            wh = Warehouse.search(domain, limit=1)

        cache[key] = wh or False
        return cache[key]
    def action_refresh_po_lot_cost(self):
        """Rebuild lot/PO cost lines and warehouse summary for the selected product(s)."""
        for rec in self:
            rec._action_refresh_po_lot_cost_single()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def _action_refresh_po_lot_cost_single(self):
        self.ensure_one()
        if not self.product_variant_ids:
            raise UserError(_("Este producto no tiene variantes para analizar existencias."))

        company = self.env.company


        wh_cache = {}
        # Limpiar líneas previas para evitar duplicados/histórico en cada actualización
        self.po_lot_cost_line_ids.sudo().unlink()
        self.po_lot_cost_wh_summary_ids.sudo().unlink()

        Quant = self.env["stock.quant"].sudo()
        POLine = self.env["purchase.order.line"].sudo()
        PO = self.env["purchase.order"].sudo()


        domain = [
            ("product_id", "in", self.product_variant_ids.ids),
            ("company_id", "in", [company.id, False]),
            ("location_id.usage", "=", "internal"),
        ]

        # Obtener quants internos (cantidad física) y agregarlos por producto+lote+ubicación
        # Usamos read_group para sumar quantity y reserved_quantity directamente en SQL
        quants = Quant.search(domain)

        qty_map = {}  # (product_id, lot_id, location_id, warehouse_id) -> {'qty': x, 'reserved': y}
        Warehouse = self.env['stock.warehouse'].sudo()
        wh_cache_local = {}

        lines_to_create = []

        for q in quants:
            # agrupación base por producto+lote+ubicación (+ almacén)
            product_id = q.product_id.id
            lot_id = q.lot_id.id if q.lot_id else False
            location_id = q.location_id.id if q.location_id else False
            qty = q.quantity or 0.0
            reserved = getattr(q, 'reserved_quantity', 0.0) or 0.0
            if qty <= 0.0:
                continue

            wh = False
            if location_id:
                if location_id in wh_cache_local:
                    wh = wh_cache_local[location_id]
                else:
                    loc_rec = q.location_id
                    company = self.company_id or self.env.company
                    wh = self._get_warehouse_from_location(loc_rec, company, Warehouse, cache=wh_cache)
                    wh_cache_local[location_id] = wh

            warehouse_id = wh.id if wh else False
            key = (product_id, lot_id or False, location_id or False, warehouse_id or False)
            bucket = qty_map.get(key)
            if not bucket:
                bucket = {'qty': 0.0, 'reserved': 0.0}
                qty_map[key] = bucket
            bucket['qty'] += qty
            bucket['reserved'] += reserved
        Warehouse = self.env['stock.warehouse'].sudo()
        wh_cache_local = {}

        # Complemento: Reservadas por lote/ubicación usando stock.move.line (más consistente con "Actualizar cantidad")
        MoveLine = self.env['stock.move.line'].sudo()
        reserved_map = {}  # (product_id, lot_id, location_id, warehouse_id) -> reserved_qty
        # Dominio: movimientos con reserva en ubicaciones internas y de tránsito
        ml_domain = [
            ('product_id', 'in', self.product_variant_ids.ids),
            ('state', 'in', ['assigned', 'partially_available']),
            ('company_id', 'in', [company.id, False]),
            ('location_id.usage', 'in', ['internal']),
        ]
        move_lines = MoveLine.search(ml_domain)
        # En v18 normalmente existe reserved_uom_qty; si no, aproximamos con product_uom_qty - qty_done
        use_reserved_uom_qty = 'reserved_uom_qty' in MoveLine._fields
        for ml in move_lines:
            try:
                rqty = ml.reserved_uom_qty if use_reserved_uom_qty else ((ml.product_uom_qty or 0.0) - (ml.qty_done or 0.0))
            except Exception:
                rqty = 0.0
            if not rqty:
                continue
            loc = ml.location_id
            location_id = loc.id if loc else False
            # warehouse por ubicación
            wh = False
            if location_id:
                if location_id in wh_cache_local:
                    wh = wh_cache_local[location_id]
                else:
                    wh = self._get_warehouse_from_location(loc, company, Warehouse)
                    wh_cache_local[location_id] = wh
            warehouse_id = wh.id if wh else False
            key = (ml.product_id.id, ml.lot_id.id if ml.lot_id else False, location_id or False, warehouse_id or False)
            reserved_map[key] = reserved_map.get(key, 0.0) + rqty

        # Mezclamos las reservadas del mapa al qty_map (manteniendo qty físico de quants)
        for key, rqty in reserved_map.items():
            bucket = qty_map.get(key)
            if not bucket:
                # Si no existe bucket (por ejemplo reserva en ubicación sin quant), creamos bucket con qty=0
                bucket = {'qty': 0.0, 'reserved': 0.0}
                qty_map[key] = bucket
            bucket['reserved'] = (bucket.get('reserved') or 0.0) + rqty
        for (product_id, lot_id, location_id, warehouse_id), bq in qty_map.items():
            qty = bq.get('qty', 0.0)
            reserved = bq.get('reserved', 0.0)

            if qty <= 0 or not product_id:
                continue

            product = self.env["product.product"].browse(product_id)
            lot = self.env["stock.lot"].browse(lot_id) if lot_id else False

            purchase_order = False
            po_line = False
            currency = company.currency_id
            price_unit = 0.0
            vendor = False
            date_order = False
            note = False

            if lot and lot.name:
                purchase_order = PO.search([("name", "=", lot.name), ("company_id", "=", company.id)], limit=1)

                if purchase_order:
                    po_line = POLine.search([
                        ("order_id", "=", purchase_order.id),
                        ("product_id", "=", product_id),
                    ], order="id desc", limit=1)

                    if po_line:
                        currency = po_line.currency_id or purchase_order.currency_id or currency
                        price_unit = po_line.price_unit or 0.0
                        vendor = purchase_order.partner_id
                        date_order = purchase_order.date_order
                        if po_line.product_uom and po_line.product_uom != product.uom_id:
                            note = _("UdM OC: %s, UdM producto: %s (revisar conversión)") % (
                                po_line.product_uom.display_name, product.uom_id.display_name
                            )
                    else:
                        note = _("No se encontró línea de OC para este producto en %s") % (purchase_order.name,)
                else:
                    note = _("No se encontró Orden de Compra con nombre = lote (%s)") % lot.name
            else:
                note = _("Sin lote: no se puede ligar a OC (por estándar: lote=PO)")

            lines_to_create.append({
                "company_id": company.id,
                "product_tmpl_id": self.id,
                "product_id": product_id,
                "lot_id": lot_id or False,
                "location_id": location_id or False,
                "purchase_order_id": purchase_order.id if purchase_order else False,
                "purchase_order_line_id": po_line.id if po_line else False,
                "vendor_id": vendor.id if vendor else False,
                "date_order": date_order,
                "qty_available": qty,
                "reserved_qty": reserved,
                "uom_id": product.uom_id.id,
                "currency_id": currency.id if currency else company.currency_id.id,
                "price_unit": price_unit,
                "note": note,
            })

        created_lines = self.env["product.po.lot.cost.line"]
        if lines_to_create:
            created_lines = self.env["product.po.lot.cost.line"].sudo().create(lines_to_create)

        # Resumen por almacén (en moneda de la compañía)
        company_currency = company.currency_id
        today = fields.Date.today()
        summary_map = {}  # warehouse_name -> {'warehouse_id': id/False, 'qty': x, 'reserved': y, 'value': y}
        for line in created_lines:
            wh_id = line.warehouse_id.id if line.warehouse_id else False
            wh_name = (line.warehouse_id.display_name if line.warehouse_id else False)
            if not wh_name:
                # fallback: primer nivel de la ubicación (ej. MX, MXMAY, AJUST)
                wh_name = (line.location_id.complete_name.split('/')[0].strip() if line.location_id and line.location_id.complete_name else 'Sin almacén')
                # intentar traducir prefijo (MX, MXMAY, etc.) al nombre del almacén
                if wh_name and wh_name not in ('Sin almacén',):
                    wh2 = self.env['stock.warehouse'].sudo().search([('code', '=', wh_name), ('company_id', 'in', [company.id, False])], limit=1)
                    if not wh2:
                        wh2 = self.env['stock.warehouse'].sudo().search([('code', '=', wh_name)], limit=1)
                    if wh2:
                        wh_id = wh2.id
                        wh_name = wh2.display_name
            qty = line.qty_available or 0.0
            val = (line.qty_available or 0.0) * (line.price_unit or 0.0)
            if line.currency_id and line.currency_id != company_currency:
                val = line.currency_id._convert(val, company_currency, company, today)
            bucket = summary_map.setdefault(wh_name, {'warehouse_id': wh_id, 'qty': 0.0, 'reserved': 0.0, 'value': 0.0})
            bucket['qty'] += qty
            bucket['reserved'] += (line.reserved_qty or 0.0)
            bucket['value'] += val

        summary_vals = []
        for wh_name, b in summary_map.items():
            wh_id = b.get('warehouse_id') or False
            summary_vals.append({
                'company_id': company.id,
                'product_tmpl_id': self.id,
                'warehouse_id': wh_id,
                'warehouse_name': wh_name,
                'reserved_total': b['reserved'],
                'qty_total': b['qty'],
                'currency_id': company_currency.id,
                'value_total': b['value'],
            })

        if summary_vals:
            self.env["product.po.lot.cost.wh.summary"].sudo().create(summary_vals)

        return {"type": "ir.actions.client", "tag": "reload"}