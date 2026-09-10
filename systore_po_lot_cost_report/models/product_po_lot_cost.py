# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


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

    is_transit = fields.Boolean(string='En tránsito', readonly=True, index=True)
    transit_state = fields.Selection([
        ('stock', 'Stock'),
        ('transit', 'Tránsito'),
    ], string='Estado', default='stock', readonly=True, index=True)

    purchase_order_id = fields.Many2one("purchase.order", string="Orden de compra", index=True)
    purchase_order_line_id = fields.Many2one("purchase.order.line", string="Línea OC", index=True)
    vendor_id = fields.Many2one("res.partner", string="Proveedor", index=True)
    date_order = fields.Datetime(string="Fecha OC", index=True)
    inventory_entry_date = fields.Date(string="Fecha de ingreso", readonly=True, index=True)
    inventory_days = fields.Integer(
        string="Días en inventario",
        compute="_compute_inventory_days",
        store=False,
        help="Días transcurridos desde la primera recepción validada desde Proveedor hacia una ubicación interna. En tránsito se muestra 0.",
    )
    location_since_date = fields.Date(
        string="Desde ubicación",
        readonly=True,
        index=True,
        help="Fecha desde la que el lote mantiene existencia positiva de forma continua en la ubicación actual.",
    )
    location_days = fields.Integer(
        string="Días en ubicación",
        compute="_compute_location_days",
        store=False,
        help="Días que el lote ha permanecido de forma continua en la ubicación actual. Una entrada parcial adicional no reinicia el contador; si el lote sale completamente y vuelve a entrar, el contador comienza de nuevo.",
    )

    qty_available = fields.Float(string="Cantidad reporte", digits="Product Unit of Measure")
    qty_on_hand = fields.Float(string="Piezas a la mano", digits="Product Unit of Measure", readonly=True)
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

    @api.depends("inventory_entry_date", "is_transit")
    def _compute_inventory_days(self):
        for rec in self:
            if rec.is_transit or not rec.inventory_entry_date:
                rec.inventory_days = 0
                continue
            today = fields.Date.context_today(rec)
            rec.inventory_days = max((today - rec.inventory_entry_date).days, 0)

    @api.depends("location_since_date", "is_transit")
    def _compute_location_days(self):
        for rec in self:
            if rec.is_transit or not rec.location_since_date:
                rec.location_days = 0
                continue
            today = fields.Date.context_today(rec)
            rec.location_days = max((today - rec.location_since_date).days, 0)


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

    systore_is_open_box = fields.Boolean(
        string="¿Es open box?",
        help="Cuando está activo, el reporte toma el costo desde el SKU origen y aplica el descuento operativo de Open Box.",
    )
    systore_open_box_origin_sku = fields.Char(
        string="SKU Origen",
        help="SKU del producto original usado para localizar la línea de Orden de Compra y calcular el costo del Open Box.",
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

    def _systore_get_open_box_origin_product(self):
        """Return the origin product used to cost Open Box items.

        Open Box SKUs do not appear in purchase orders. When the product is
        marked as Open Box, we use SKU Origen to find the original product in
        purchase.order.line and then apply a 15% discount to that purchase cost.
        """
        self.ensure_one()
        if not self.systore_is_open_box:
            return False
        origin_sku = (self.systore_open_box_origin_sku or '').strip()
        if not origin_sku:
            return False
        return self.env['product.product'].sudo().with_context(active_test=False).search([
            ('default_code', '=', origin_sku),
            ('company_id', 'in', [self.company_id.id if self.company_id else self.env.company.id, False]),
        ], limit=1)

    def _systore_apply_open_box_cost_rule(self, price_unit):
        """Open Box operational cost rule: origin purchase cost less 15%."""
        self.ensure_one()
        if self.systore_is_open_box:
            return (price_unit or 0.0) * 0.85
        return price_unit or 0.0

    def _systore_get_first_inventory_entry_date(self, lot, product, purchase_order=False):
        """Return the first validated Vendor -> Internal receipt date for a lot/product.

        The current warehouse is intentionally ignored: once the merchandise enters
        an internal location, later internal transfers must not reset its age.

        For Open Box, ``product`` is the configured origin SKU and the lookup is done
        by lot *name*, not lot record id. This lets an Open Box lot keep the age of the
        original purchased SKU even when the transformation creates another stock.lot
        record for the new product.
        """
        self.ensure_one()
        if not lot or not lot.name or not product:
            return False

        company = self.company_id or self.env.company
        MoveLine = self.env['stock.move.line'].sudo()
        Move = self.env['stock.move'].sudo()

        base_domain = [
            ('state', '=', 'done'),
            ('company_id', 'in', [company.id, False]),
            ('product_id', '=', product.id),
            ('lot_id.name', '=', lot.name),
            ('location_id.usage', '=', 'supplier'),
            ('location_dest_id.usage', '=', 'internal'),
        ]

        move_lines = MoveLine.browse([])
        # When purchase_stock is present, this makes the PO relationship explicit.
        # We keep a fallback without it for historical/custom receipts where that
        # relation may not have been preserved.
        if purchase_order and 'purchase_line_id' in Move._fields:
            move_lines = MoveLine.search(base_domain + [
                ('move_id.purchase_line_id.order_id', '=', purchase_order.id),
            ])
        if not move_lines:
            move_lines = MoveLine.search(base_domain)

        first_dt = False
        for ml in move_lines:
            candidate = False
            picking = ml.picking_id
            if picking and 'date_done' in picking._fields and picking.date_done:
                candidate = picking.date_done
            elif 'date' in ml._fields and ml.date:
                candidate = ml.date
            elif ml.move_id and 'date' in ml.move_id._fields and ml.move_id.date:
                candidate = ml.move_id.date

            if not candidate:
                continue
            candidate = fields.Datetime.to_datetime(candidate)
            if not first_dt or candidate < first_dt:
                first_dt = candidate

        if not first_dt:
            return False

        # Store only the calendar date shown to the user; convert using the active
        # user's timezone so a receipt around midnight is displayed consistently.
        return fields.Datetime.context_timestamp(self, first_dt).date()

    def _systore_get_location_since_date(self, lot, product, location, current_qty):
        """Return the start date of the current continuous stay in ``location``.

        Starting from the quantity that exists now for the product/lot/location, we
        replay completed move lines backwards.  The relevant date is the inbound
        movement that changed the historical balance from zero (or negative) to
        positive for the *current* uninterrupted stay.  Therefore:

        * a later partial inbound does not reset the age while older units remain;
        * a transfer that empties the lot from the location ends that stay; and
        * when the lot returns later, the counter starts from the new inbound date.

        This is intentionally independent from the PO.  The PO determines the global
        inventory age, while the stock movement history determines location age.
        """
        self.ensure_one()
        if not lot or not product or not location or not current_qty or current_qty <= 0:
            return False

        company = self.company_id or self.env.company
        MoveLine = self.env['stock.move.line'].sudo()
        domain = [
            ('state', '=', 'done'),
            ('company_id', 'in', [company.id, False]),
            ('product_id', '=', product.id),
            ('lot_id', '=', lot.id),
            '|',
                ('location_id', '=', location.id),
                ('location_dest_id', '=', location.id),
        ]
        if 'quantity_product_uom' in MoveLine._fields:
            domain.insert(4, ('quantity_product_uom', '>', 0.0))

        move_lines = MoveLine.search(domain, order='date desc, id desc')
        if not move_lines:
            # Defensive fallback for historical migrations that recreated lot records
            # while preserving the visible lot name.
            fallback_domain = [
                ('state', '=', 'done'),
                ('company_id', 'in', [company.id, False]),
                ('product_id', '=', product.id),
                ('lot_id.name', '=', lot.name),
                '|',
                    ('location_id', '=', location.id),
                    ('location_dest_id', '=', location.id),
            ]
            if 'quantity_product_uom' in MoveLine._fields:
                fallback_domain.insert(4, ('quantity_product_uom', '>', 0.0))
            move_lines = MoveLine.search(fallback_domain, order='date desc, id desc')

        qty_after = float(current_qty)
        rounding = product.uom_id.rounding or 0.01
        epsilon = rounding / 2.0

        for ml in move_lines:
            if 'quantity_product_uom' in ml._fields:
                qty = ml.quantity_product_uom or 0.0
            else:
                qty = ml.product_uom_id._compute_quantity(ml.quantity or 0.0, product.uom_id)
            if qty <= 0.0:
                continue

            entered = ml.location_dest_id.id == location.id and ml.location_id.id != location.id
            left = ml.location_id.id == location.id and ml.location_dest_id.id != location.id
            if not entered and not left:
                continue

            if entered:
                qty_before = qty_after - qty
                # This inbound movement started the current uninterrupted positive
                # balance in the location.
                if qty_after > epsilon and qty_before <= epsilon:
                    event_dt = ml.date or (ml.picking_id.date_done if ml.picking_id else False)
                    if event_dt:
                        event_dt = fields.Datetime.to_datetime(event_dt)
                        return fields.Datetime.context_timestamp(self, event_dt).date()
                qty_after = qty_before
            elif left:
                # Going backwards, an outbound movement adds the quantity back.
                qty_after += qty

        return False

    def _systore_refresh_po_lot_cost_no_reload(self):
        """Rebuild report lines without returning a UI reload action.

        Used by automatic hooks such as purchase.order.button_confirm.
        """
        for rec in self:
            rec._action_refresh_po_lot_cost_single()
        return True

    def action_refresh_po_lot_cost(self):
        """Rebuild lot/PO cost lines and warehouse summary for the selected product(s)."""
        self._systore_refresh_po_lot_cost_no_reload()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def _get_move_pending_qty_in_product_uom(self, move, product):
        """Return pending quantity from an incoming stock.move in product default UoM.

        Odoo versions/customizations may expose done/reserved quantities with slightly
        different technical fields. This helper keeps the module tolerant while using
        the same purchase cost method: pending units * purchase.order.line.price_unit.
        """
        ordered_qty = move.product_uom_qty or 0.0

        done_qty = 0.0
        if 'quantity_done' in move._fields:
            done_qty = move.quantity_done or 0.0
        # En movimientos abiertos de recepción no descontamos reservas/asignaciones: lo
        # relevante es lo pendiente de llegar. Si hubo recepción parcial, Odoo normalmente
        # deja el movimiento abierto con la cantidad restante.

        pending = max(ordered_qty - done_qty, 0.0)
        move_uom = move.product_uom or product.uom_id
        if move_uom and move_uom != product.uom_id:
            pending = move_uom._compute_quantity(pending, product.uom_id)
        return pending

    def _action_refresh_po_lot_cost_single(self):
        self.ensure_one()
        if not self.product_variant_ids:
            raise UserError(_("Este producto no tiene variantes para analizar existencias."))

        company = self.env.company
        open_box_origin_product = self._systore_get_open_box_origin_product()


        wh_cache = {}
        entry_date_cache = {}  # (lot_name, lookup_product_id, purchase_order_id) -> date/False
        location_since_cache = {}  # (lot_id, product_id, location_id, rounded_current_qty) -> date/False
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
            inventory_entry_date = False
            location_since_date = False
            note = False

            if lot and lot.name:
                purchase_order = PO.search([("name", "=", lot.name), ("company_id", "=", company.id)], limit=1)

                if purchase_order:
                    cost_lookup_product = open_box_origin_product if self.systore_is_open_box and open_box_origin_product else product
                    po_line = POLine.search([
                        ("order_id", "=", purchase_order.id),
                        ("product_id", "=", cost_lookup_product.id),
                    ], order="id desc", limit=1)

                    if po_line:
                        currency = po_line.currency_id or purchase_order.currency_id or currency
                        price_unit = self._systore_apply_open_box_cost_rule(po_line.price_unit or 0.0)
                        vendor = purchase_order.partner_id
                        date_order = purchase_order.date_order
                        notes = []
                        if self.systore_is_open_box:
                            if open_box_origin_product:
                                notes.append(_("Open Box: costo tomado del SKU origen %s menos 15%%") % (open_box_origin_product.default_code or open_box_origin_product.display_name,))
                            else:
                                notes.append(_("Open Box: falta configurar SKU Origen válido"))
                        if po_line.product_uom and po_line.product_uom != product.uom_id:
                            notes.append(_("UdM OC: %s, UdM producto: %s (revisar conversión)") % (
                                po_line.product_uom.display_name, product.uom_id.display_name
                            ))
                        note = ". ".join(notes) if notes else False
                    else:
                        if self.systore_is_open_box:
                            if open_box_origin_product:
                                note = _("Open Box: no se encontró línea de OC para el SKU origen %s en %s") % (open_box_origin_product.default_code or open_box_origin_product.display_name, purchase_order.name)
                            else:
                                note = _("Open Box: falta configurar SKU Origen válido")
                        else:
                            note = _("No se encontró línea de OC para este producto en %s") % (purchase_order.name,)
                else:
                    note = _("No se encontró Orden de Compra con nombre = lote (%s)") % lot.name
            else:
                note = _("Sin lote: no se puede ligar a OC (por estándar: lote=PO)")

            if lot and lot.name:
                entry_lookup_product = open_box_origin_product if self.systore_is_open_box and open_box_origin_product else product
                cache_key = (
                    lot.name,
                    entry_lookup_product.id if entry_lookup_product else False,
                    purchase_order.id if purchase_order else False,
                )
                if cache_key not in entry_date_cache:
                    entry_date_cache[cache_key] = self._systore_get_first_inventory_entry_date(
                        lot, entry_lookup_product, purchase_order=purchase_order
                    )
                inventory_entry_date = entry_date_cache[cache_key]

                if not inventory_entry_date:
                    missing_entry_note = _("No se encontró una recepción validada Proveedor → Interno para calcular antigüedad")
                    note = ". ".join([n for n in [note, missing_entry_note] if n])

                if location_id:
                    current_location = self.env['stock.location'].browse(location_id)
                    loc_cache_key = (
                        lot.id,
                        product.id,
                        current_location.id,
                        round(qty, 6),
                    )
                    if loc_cache_key not in location_since_cache:
                        location_since_cache[loc_cache_key] = self._systore_get_location_since_date(
                            lot, product, current_location, qty
                        )
                    location_since_date = location_since_cache[loc_cache_key]
                    if not location_since_date:
                        missing_loc_note = _("No se encontró historial suficiente para calcular días en la ubicación actual")
                        note = ". ".join([n for n in [note, missing_loc_note] if n])

            lines_to_create.append({
                "company_id": company.id,
                "product_tmpl_id": self.id,
                "product_id": product_id,
                "lot_id": lot_id or False,
                "location_id": location_id or False,
                "warehouse_id": warehouse_id or False,
                "purchase_order_id": purchase_order.id if purchase_order else False,
                "purchase_order_line_id": po_line.id if po_line else False,
                "vendor_id": vendor.id if vendor else False,
                "date_order": date_order,
                "inventory_entry_date": inventory_entry_date,
                "location_since_date": location_since_date,
                "qty_available": qty,
                "qty_on_hand": max(qty - reserved, 0.0),
                "reserved_qty": reserved,
                "uom_id": product.uom_id.id,
                "currency_id": currency.id if currency else company.currency_id.id,
                "price_unit": price_unit,
                "is_transit": False,
                "transit_state": "stock",
                "note": note,
            })

        # Complemento: compras confirmadas pendientes de recibir.
        # Se muestran como "Tránsito" tomando la ubicación destino del movimiento de recepción.
        po_line_domain = [
            ('order_id.state', 'in', ['purchase', 'done']),
            ('order_id.company_id', '=', company.id),
            ('product_id', 'in', self.product_variant_ids.ids),
        ]
        po_lines_pending = POLine.search(po_line_domain)
        for po_line in po_lines_pending:
            product = po_line.product_id
            if not product:
                continue

            # Preferimos movimientos reales de recepción porque ahí está la ubicación destino.
            pending_by_dest = {}  # (location_id, warehouse_id) -> qty pending in product.uom_id
            moves = po_line.move_ids.filtered(lambda m: m.state not in ('done', 'cancel') and m.location_dest_id and m.location_dest_id.usage == 'internal')
            for move in moves:
                pending_qty = self._get_move_pending_qty_in_product_uom(move, product)
                if pending_qty <= 0.0:
                    continue
                dest = move.location_dest_id
                wh = self._get_warehouse_from_location(dest, company, Warehouse, cache=wh_cache) if dest else False
                key = (dest.id if dest else False, wh.id if wh else False)
                pending_by_dest[key] = pending_by_dest.get(key, 0.0) + pending_qty

            # Fallback: si aún no hay movimientos de recepción, usamos qty pendiente de la línea
            # y tratamos de resolver el almacén desde picking_type/default_location_dest_id.
            if not pending_by_dest:
                ordered_qty = po_line.product_uom._compute_quantity(po_line.product_qty or 0.0, product.uom_id) if po_line.product_uom and po_line.product_uom != product.uom_id else (po_line.product_qty or 0.0)
                received_qty = po_line.product_uom._compute_quantity(po_line.qty_received or 0.0, product.uom_id) if po_line.product_uom and po_line.product_uom != product.uom_id else (po_line.qty_received or 0.0)
                pending_qty = max(ordered_qty - received_qty, 0.0)
                if pending_qty > 0.0:
                    picking_type = po_line.order_id.picking_type_id
                    dest = picking_type.default_location_dest_id if picking_type else False
                    wh = picking_type.warehouse_id if picking_type and picking_type.warehouse_id else (self._get_warehouse_from_location(dest, company, Warehouse, cache=wh_cache) if dest else False)
                    key = (dest.id if dest else False, wh.id if wh else False)
                    pending_by_dest[key] = pending_by_dest.get(key, 0.0) + pending_qty

            for (location_id, warehouse_id), pending_qty in pending_by_dest.items():
                if pending_qty <= 0.0:
                    continue
                currency = po_line.currency_id or po_line.order_id.currency_id or company.currency_id
                note = _('Compra confirmada pendiente de recibir')
                if po_line.product_uom and po_line.product_uom != product.uom_id:
                    note = _('%s. UdM OC: %s, UdM producto: %s') % (note, po_line.product_uom.display_name, product.uom_id.display_name)
                lines_to_create.append({
                    'company_id': company.id,
                    'product_tmpl_id': self.id,
                    'product_id': product.id,
                    'lot_id': False,
                    'location_id': location_id or False,
                    'warehouse_id': warehouse_id or False,
                    'purchase_order_id': po_line.order_id.id,
                    'purchase_order_line_id': po_line.id,
                    'vendor_id': po_line.order_id.partner_id.id if po_line.order_id.partner_id else False,
                    'date_order': po_line.order_id.date_order,
                    # Todavía no ha ingresado físicamente: no inicia antigüedad.
                    'inventory_entry_date': False,
                    'location_since_date': False,
                    'qty_available': pending_qty,
                    # En tránsito todavía no está físicamente a la mano.
                    # La columna permite comparar lo pendiente contra lo realmente disponible.
                    'qty_on_hand': 0.0,
                    'reserved_qty': 0.0,
                    'uom_id': product.uom_id.id,
                    'currency_id': currency.id,
                    'price_unit': po_line.price_unit or 0.0,
                    'is_transit': True,
                    'transit_state': 'transit',
                    'note': note,
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
            if line.is_transit:
                wh_name = _('%s / Tránsito') % (wh_name or 'Sin almacén')
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


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _action_done(self):
        """Refresh the report after any completed transfer touching internal stock.

        Receipts update Tránsito and global inventory age. Internal transfers update
        the current location and restart location age only when the lot had actually
        left the destination before returning. Deliveries also refresh the report so
        quantities/locations do not remain stale.

        A savepoint protects the core stock validation flow: the operational report
        must never block a warehouse transfer.
        """
        affected_templates = self.move_ids.filtered(
            lambda m: m.location_id.usage == 'internal' or m.location_dest_id.usage == 'internal'
        ).mapped('product_id.product_tmpl_id')

        res = super()._action_done()

        if affected_templates:
            try:
                with self.env.cr.savepoint():
                    affected_templates.sudo()._systore_refresh_po_lot_cost_no_reload()
            except Exception:
                _logger.exception("Could not refresh PO/Lot cost report after stock transfer validation")
        return res


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _systore_refresh_po_lot_cost_products(self):
        """Refresh the PO/Lot cost report for products affected by this PO.

        The report is stored on product.template, so after confirming a PO we
        rebuild the related product lines to immediately show the new tránsito.
        """
        templates = self.mapped('order_line.product_id.product_tmpl_id')
        if templates:
            templates.sudo()._systore_refresh_po_lot_cost_no_reload()

    def button_confirm(self):
        res = super().button_confirm()
        self._systore_refresh_po_lot_cost_products()
        return res


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        confirmed_lines = lines.filtered(lambda l: l.order_id.state in ('purchase', 'done'))
        templates = confirmed_lines.mapped('product_id.product_tmpl_id')
        if templates:
            templates.sudo()._systore_refresh_po_lot_cost_no_reload()
        return lines

    def write(self, vals):
        old_templates = self.mapped('product_id.product_tmpl_id')
        res = super().write(vals)
        fields_that_affect_report = {'product_id', 'product_qty', 'qty_received', 'product_uom', 'price_unit', 'order_id'}
        if fields_that_affect_report.intersection(vals):
            lines = self.filtered(lambda l: l.order_id.state in ('purchase', 'done'))
            templates = old_templates | lines.mapped('product_id.product_tmpl_id')
            if templates:
                templates.sudo()._systore_refresh_po_lot_cost_no_reload()
        return res

