from collections import defaultdict

from odoo import api, fields, models


CHANNEL_SELECTION = [
    ("wholesale", "Mayoreo"),
    ("retail", "Minorista"),
]


class SystoreSupplyPurchaseLine(models.Model):
    _name = "systore.supply.purchase.line"
    _description = "Análisis de recepción de compras"
    _order = "report_date desc, purchase_order_name desc, product_id"
    _rec_name = "purchase_order_name"

    company_id = fields.Many2one("res.company", required=True, index=True, readonly=True)
    currency_id = fields.Many2one("res.currency", required=True, readonly=True)
    purchase_order_id = fields.Many2one("purchase.order", string="Orden de compra", index=True, readonly=True, ondelete="cascade")
    purchase_line_id = fields.Many2one("purchase.order.line", string="Línea de compra", readonly=True, ondelete="cascade")
    purchase_order_name = fields.Char(string="Orden de compra", index=True, readonly=True)
    supplier_id = fields.Many2one("res.partner", string="Proveedor", index=True, readonly=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="Almacén", index=True, readonly=True)
    channel = fields.Selection(CHANNEL_SELECTION, string="Canal", index=True, readonly=True)
    product_id = fields.Many2one("product.product", string="Producto", index=True, readonly=True)
    sku = fields.Char(string="SKU", index=True, readonly=True)
    order_state = fields.Selection(related="purchase_order_id.state", string="Estado OC", readonly=True)
    purchase_origin = fields.Selection(
        [("national", "Nacional"), ("international", "Internacional")],
        string="Origen",
        index=True,
        readonly=True,
    )
    order_date = fields.Datetime(string="Fecha de orden", readonly=True)
    first_receipt_date = fields.Datetime(string="Primera recepción", index=True, readonly=True)
    report_date = fields.Date(string="Fecha del reporte", index=True, readonly=True)
    has_receipt = fields.Boolean(string="Con recepción", index=True, readonly=True)

    ordered_qty = fields.Float(string="Piezas en orden", readonly=True)
    received_qty = fields.Float(string="Piezas recibidas (brutas)", readonly=True)
    returned_qty = fields.Float(string="Piezas devueltas", readonly=True)
    net_received_qty = fields.Float(string="Piezas recibidas netas", readonly=True)
    pending_qty = fields.Float(string="Piezas pendientes", readonly=True)
    overreceived_qty = fields.Float(string="Excedente recibido", readonly=True)
    reception_percent = fields.Float(string="% recepción", readonly=True, group_operator="avg")
    movement_status = fields.Selection(
        [
            ("pending", "Pendiente de recepción"),
            ("received", "Recepción"),
            ("vendor_return", "Devolución a proveedor"),
        ],
        string="Estado del movimiento",
        index=True,
        readonly=True,
    )
    return_picking_ids = fields.Many2many(
        "stock.picking",
        string="Transferencias de devolución",
        readonly=True,
    )
    last_return_date = fields.Datetime(
        string="Última devolución a proveedor",
        index=True,
        readonly=True,
    )

    gross_usd_unit = fields.Float(string="Mercancía USD/u", readonly=True)
    shipping_usd_unit = fields.Float(string="Logística USD/u", readonly=True)
    gross_mxn_unit = fields.Monetary(string="Mercancía MXN/u", currency_field="currency_id", readonly=True)
    shipping_mxn_unit = fields.Monetary(string="Logística MXN/u", currency_field="currency_id", readonly=True)
    import_mxn_unit = fields.Monetary(string="Importación MXN/u", currency_field="currency_id", readonly=True)
    landed_cost_mxn_unit = fields.Monetary(string="Costo global MXN/u", currency_field="currency_id", readonly=True)

    merchandise_usd_total = fields.Float(string="Mercancía USD", readonly=True)
    shipping_usd_total = fields.Float(string="Logística USD", readonly=True)
    ordered_value_mxn = fields.Monetary(string="Valor ordenado MXN", currency_field="currency_id", readonly=True)
    received_value_mxn = fields.Monetary(string="Valor recibido MXN", currency_field="currency_id", readonly=True)
    pending_value_mxn = fields.Monetary(string="Valor pendiente MXN", currency_field="currency_id", readonly=True)

    payment_status = fields.Selection(
        [("pending", "Pendiente"), ("partial", "Parcial"), ("paid", "Pagada")],
        string="Estado de pago",
        index=True,
        readonly=True,
    )
    amount_payable_mxn = fields.Monetary(string="Proveedor a pagar MXN", currency_field="currency_id", readonly=True)
    amount_payable_usd = fields.Float(string="Proveedor a pagar USD", readonly=True)
    amount_paid_mxn = fields.Monetary(string="Pagado al proveedor MXN", currency_field="currency_id", readonly=True)
    amount_paid_usd = fields.Float(string="Pagado al proveedor USD", readonly=True)
    amount_pending_mxn = fields.Monetary(string="Pendiente con proveedor MXN", currency_field="currency_id", readonly=True)
    amount_pending_usd = fields.Float(string="Pendiente con proveedor USD", readonly=True)
    effective_exchange_rate = fields.Float(string="TC efectivo ponderado", readonly=True, digits=(16, 4))

    @api.model
    def _first_receipt_date(self, order):
        moves = order.order_line.move_ids.filtered(
            lambda move: (
                move.state == "done"
                and move.location_id.usage == "supplier"
                and move.location_dest_id.usage == "internal"
            )
        )
        if not moves:
            moves = self.env["stock.move"].search([
                ("picking_id.origin", "=", order.name),
                ("company_id", "=", order.company_id.id),
                ("state", "=", "done"),
                ("location_id.usage", "=", "supplier"),
                ("location_dest_id.usage", "=", "internal"),
            ])
        dates = [
            move.picking_id.date_done or move.date
            for move in moves
            if move.picking_id.date_done or move.date
        ]
        return min(dates) if dates else False

    @api.model
    def _move_done_qty(self, move):
        if "quantity" in move._fields:
            return move.quantity or 0.0
        quantities = 0.0
        for move_line in move.move_line_ids:
            if "quantity" in move_line._fields:
                quantities += move_line.quantity or 0.0
            elif "qty_done" in move_line._fields:
                quantities += move_line.qty_done or 0.0
        return quantities or move.product_uom_qty or 0.0

    @api.model
    def _line_receipt_quantities(self, line):
        StockMove = self.env["stock.move"].sudo()
        line_moves = line.move_ids.filtered(lambda move: move.state == "done")
        receipt_moves = line_moves.filtered(
            lambda move: (
                move.location_id.usage == "supplier"
                and move.location_dest_id.usage == "internal"
            )
        )
        return_moves = line_moves.filtered(
            lambda move: (
                move.location_id.usage == "internal"
                and move.location_dest_id.usage == "supplier"
            )
        )
        if receipt_moves:
            return_moves |= StockMove.search([
                ("state", "=", "done"),
                ("origin_returned_move_id", "in", receipt_moves.ids),
                ("location_id.usage", "=", "internal"),
                ("location_dest_id.usage", "=", "supplier"),
            ])

        def line_uom_qty(move):
            qty = self._move_done_qty(move)
            if move.product_uom and line.product_uom and move.product_uom != line.product_uom:
                qty = move.product_uom._compute_quantity(qty, line.product_uom)
            return qty

        gross = sum(line_uom_qty(move) for move in receipt_moves)
        returned = sum(line_uom_qty(move) for move in return_moves)
        return gross, returned, max(gross - returned, 0.0), return_moves

    @api.model
    def _rebuild_snapshot(self, company, period):
        StockMove = self.env["stock.move"].sudo()
        receipt_moves = StockMove.search([
            ("company_id", "=", company.id),
            ("state", "=", "done"),
            ("location_id.usage", "=", "supplier"),
            ("location_dest_id.usage", "=", "internal"),
            ("date", ">=", period["utc_start"]),
            ("date", "<", period["utc_end"]),
        ])
        return_moves = StockMove.search([
            ("company_id", "=", company.id),
            ("state", "=", "done"),
            ("location_dest_id.usage", "=", "supplier"),
            ("location_id.usage", "=", "internal"),
            ("date", ">=", period["utc_start"]),
            ("date", "<", period["utc_end"]),
        ])
        orders = self.env["purchase.order"].sudo()
        if "purchase_line_id" in StockMove._fields:
            orders |= (receipt_moves | return_moves).mapped("purchase_line_id.order_id")
        if "origin_returned_move_id" in StockMove._fields:
            orders |= return_moves.mapped("origin_returned_move_id.purchase_line_id.order_id")
        origins = list(set(filter(None, receipt_moves.mapped("picking_id.origin"))))
        if origins:
            orders |= self.env["purchase.order"].sudo().search([
                ("company_id", "=", company.id),
                ("name", "in", origins),
            ])
        orders = orders.filtered(
            lambda order: (
                order.state in ("purchase", "done")
                and self._first_receipt_date(order)
            )
        )

        rows_in_month = self.sudo().search([
            ("company_id", "=", company.id),
            ("report_date", ">=", period["month_start"]),
            ("report_date", "<", period["month_end"]),
        ])
        rows_for_affected_orders = self.sudo().search([
            ("company_id", "=", company.id),
            ("purchase_order_id", "in", orders.ids),
        ]) if orders else self
        (rows_in_month | rows_for_affected_orders).unlink()
        values = []
        currency = company.currency_id
        for order in orders:
            first_receipt = self._first_receipt_date(order)
            report_date = fields.Date.to_date(first_receipt)
            warehouse = order.picking_type_id.warehouse_id
            if not warehouse or not warehouse._systore_is_managed_for_supply():
                continue
            destination = order.picking_type_id.default_location_dest_id
            channel = warehouse._systore_resolved_supply_channel(destination)
            purchase_origin = order._systore_resolved_purchase_origin()
            for line in order.order_line.filtered(lambda item: not item.display_type and item.product_id):
                ordered = line.product_qty or 0.0
                received, returned, net_received, line_return_moves = (
                    self._line_receipt_quantities(line)
                )
                pending = max(ordered - net_received, 0.0)
                overreceived = max(net_received - ordered, 0.0)
                landed_cost = order._systore_line_cost_mxn(line)
                reception_percent = (net_received / ordered * 100.0) if ordered else 0.0
                movement_status = (
                    "vendor_return" if returned > 0
                    else "received" if received > 0
                    else "pending"
                )
                values.append({
                    "company_id": company.id,
                    "currency_id": currency.id,
                    "purchase_order_id": order.id,
                    "purchase_line_id": line.id,
                    "purchase_order_name": order.name,
                    "supplier_id": order.partner_id.id,
                    "warehouse_id": warehouse.id if warehouse else False,
                    "channel": channel,
                    "product_id": line.product_id.id,
                    "sku": line.product_id.default_code or "",
                    "purchase_origin": purchase_origin,
                    "order_date": order.date_order,
                    "first_receipt_date": first_receipt,
                    "report_date": report_date,
                    "has_receipt": received > 0,
                    "ordered_qty": ordered,
                    "received_qty": received,
                    "returned_qty": returned,
                    "net_received_qty": net_received,
                    "pending_qty": pending,
                    "overreceived_qty": overreceived,
                    "reception_percent": reception_percent,
                    "movement_status": movement_status,
                    "return_picking_ids": [(6, 0, line_return_moves.mapped("picking_id").ids)],
                    "last_return_date": max(
                        (move.picking_id.date_done or move.date for move in line_return_moves),
                        default=False,
                    ),
                    "gross_usd_unit": line.x_gross_usd or 0.0,
                    "shipping_usd_unit": line.x_ship_usd or 0.0,
                    "gross_mxn_unit": line.x_gross_mxn or 0.0,
                    "shipping_mxn_unit": line.x_ship_mxn or 0.0,
                    "import_mxn_unit": line.x_import_mxn or 0.0,
                    "landed_cost_mxn_unit": landed_cost,
                    "merchandise_usd_total": ordered * (line.x_gross_usd or 0.0),
                    "shipping_usd_total": ordered * (line.x_ship_usd or 0.0),
                    "ordered_value_mxn": ordered * landed_cost,
                    "received_value_mxn": net_received * landed_cost,
                    "pending_value_mxn": pending * landed_cost,
                    "payment_status": order.systore_payment_status,
                    "amount_payable_mxn": order.systore_amount_payable_mxn,
                    "amount_payable_usd": order.systore_merchandise_payable_usd,
                    "amount_paid_mxn": order.systore_amount_paid_mxn,
                    "amount_paid_usd": order.systore_amount_paid_usd,
                    "amount_pending_mxn": order.systore_amount_pending_mxn,
                    "amount_pending_usd": order.systore_amount_pending_usd,
                    "effective_exchange_rate": order.systore_effective_exchange_rate,
                })
        for start in range(0, len(values), 1000):
            self.sudo().create(values[start:start + 1000])
        return len(values)


class SystoreSupplyDemandLine(models.Model):
    _name = "systore.supply.demand.line"
    _description = "Demanda de traslados parciales"
    _order = "scheduled_date, sale_order_id, sku"

    company_id = fields.Many2one("res.company", required=True, index=True, readonly=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="Almacén", required=True, index=True, readonly=True)
    channel = fields.Selection(CHANNEL_SELECTION, string="Canal", required=True, index=True, readonly=True)
    sale_order_id = fields.Many2one("sale.order", string="Orden de venta", index=True, readonly=True, ondelete="cascade")
    picking_id = fields.Many2one("stock.picking", string="Operación", index=True, readonly=True, ondelete="cascade")
    source_location_id = fields.Many2one("stock.location", string="Ubicación origen", index=True, readonly=True)
    scheduled_date = fields.Datetime(string="Fecha programada", index=True, readonly=True)
    product_id = fields.Many2one("product.product", string="Producto", required=True, index=True, readonly=True)
    sku = fields.Char(string="SKU", index=True, readonly=True)
    open_demand_qty = fields.Float(string="Piezas solicitadas", readonly=True)
    reserved_qty = fields.Float(string="Piezas listas", readonly=True)
    missing_to_buy_qty = fields.Float(string="Piezas faltantes", readonly=True)
    coverage_status = fields.Selection(
        [("partial", "Parcial")],
        string="Estado del traslado",
        index=True,
        readonly=True,
    )
    snapshot_date = fields.Datetime(string="Actualizado", readonly=True)
    period_month = fields.Date(string="Mes", index=True, readonly=True)

    @api.model
    def _convert_qty(self, qty, source_uom, product):
        if source_uom and source_uom != product.uom_id:
            return source_uom._compute_quantity(qty, product.uom_id)
        return qty

    @api.model
    def _sale_from_picking(self, picking):
        if picking.sale_id:
            return picking.sale_id
        if picking.group_id and "sale_id" in picking.group_id._fields and picking.group_id.sale_id:
            return picking.group_id.sale_id
        sale_lines = picking.move_ids_without_package.mapped("sale_line_id")
        return sale_lines[:1].order_id if sale_lines else self.env["sale.order"]

    @api.model
    def _rebuild_snapshot(self, company, period):
        self.sudo().search([
            ("company_id", "=", company.id),
            "|",
            ("period_month", "=", False),
            ("period_month", "=", period["month_start"]),
        ]).unlink()
        Picking = self.env["stock.picking"].sudo()
        pickings = Picking.search([
            ("company_id", "=", company.id),
            ("state", "not in", ["done", "cancel"]),
            ("systore_batch_readiness_state", "=", "partial"),
            ("location_id.name", "=ilike", "Existencias"),
            ("scheduled_date", ">=", period["utc_start"]),
            ("scheduled_date", "<", period["utc_end"]),
        ])
        if pickings:
            self.sudo().search([
                ("company_id", "=", company.id),
                ("picking_id", "in", pickings.ids),
                ("period_month", "!=", period["month_start"]),
            ]).unlink()
        now = fields.Datetime.now()
        values = []
        for picking in pickings:
            sale = self._sale_from_picking(picking)
            if not sale:
                continue
            warehouse = sale.warehouse_id or picking.picking_type_id.warehouse_id
            if not warehouse or not warehouse._systore_is_managed_for_supply():
                continue
            moves_by_product = defaultdict(lambda: self.env["stock.move"])
            for move in picking.move_ids_without_package.filtered(
                lambda item: item.state not in ("done", "cancel") and item.product_id
            ):
                moves_by_product[move.product_id.id] |= move
            for product_id, moves in moves_by_product.items():
                product = self.env["product.product"].browse(product_id)
                demand = 0.0
                ready = 0.0
                for move in moves:
                    move_demand = self._convert_qty(move.product_uom_qty or 0.0, move.product_uom, product)
                    move_ready = self._convert_qty(
                        picking._systore_move_ready_qty_for_batch(move),
                        move.product_uom,
                        product,
                    )
                    demand += move_demand
                    ready += min(move_ready, move_demand)
                missing = max(demand - ready, 0.0)
                if missing <= 0:
                    continue
                values.append({
                    "company_id": company.id,
                    "warehouse_id": warehouse.id,
                    "channel": warehouse._systore_resolved_supply_channel(picking.location_id),
                    "sale_order_id": sale.id,
                    "picking_id": picking.id,
                    "source_location_id": picking.location_id.id,
                    "scheduled_date": picking.scheduled_date,
                    "product_id": product.id,
                    "sku": product.default_code or "",
                    "open_demand_qty": demand,
                    "reserved_qty": ready,
                    "missing_to_buy_qty": missing,
                    "coverage_status": "partial",
                    "snapshot_date": now,
                    "period_month": period["month_start"],
                })
        for start in range(0, len(values), 1000):
            self.sudo().create(values[start:start + 1000])
        return len(values)


class SystoreSupplyTraceLine(models.Model):
    _name = "systore.supply.trace.line"
    _description = "Trazabilidad compra a venta por lote"
    _order = "movement_date desc, id desc"

    company_id = fields.Many2one("res.company", required=True, index=True, readonly=True)
    currency_id = fields.Many2one("res.currency", required=True, readonly=True)
    purchase_order_id = fields.Many2one("purchase.order", string="Orden de compra", index=True, readonly=True, ondelete="cascade")
    sale_order_id = fields.Many2one("sale.order", string="Orden de venta", index=True, readonly=True, ondelete="cascade")
    picking_id = fields.Many2one("stock.picking", string="Transferencia", readonly=True, ondelete="cascade")
    move_line_id = fields.Many2one("stock.move.line", string="Movimiento", readonly=True, ondelete="cascade")
    lot_id = fields.Many2one("stock.lot", string="Lote / OC", index=True, readonly=True)
    supplier_id = fields.Many2one("res.partner", string="Proveedor", index=True, readonly=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="Almacén", index=True, readonly=True)
    channel = fields.Selection(CHANNEL_SELECTION, string="Canal", index=True, readonly=True)
    product_id = fields.Many2one("product.product", string="Producto", index=True, readonly=True)
    sku = fields.Char(string="SKU", index=True, readonly=True)
    quantity = fields.Float(string="Piezas", readonly=True)
    unit_cost_mxn = fields.Monetary(string="Costo global MXN/u", currency_field="currency_id", readonly=True)
    total_cost_mxn = fields.Monetary(string="Costo total MXN", currency_field="currency_id", readonly=True)
    movement_date = fields.Datetime(string="Fecha de salida", index=True, readonly=True)

    @api.model
    def _sale_from_move_line(self, move_line):
        move = move_line.move_id
        if "sale_line_id" in move._fields and move.sale_line_id:
            return move.sale_line_id.order_id
        picking = move_line.picking_id or move.picking_id
        if picking and "sale_id" in picking._fields and picking.sale_id:
            return picking.sale_id
        if picking and picking.group_id and "sale_id" in picking.group_id._fields:
            return picking.group_id.sale_id
        return self.env["sale.order"]

    @api.model
    def _move_line_qty(self, move_line):
        if "quantity" in move_line._fields:
            return move_line.quantity or 0.0
        if "qty_done" in move_line._fields:
            return move_line.qty_done or 0.0
        return 0.0

    @api.model
    def _po_product_cost(self, order, product):
        lines = order.order_line.filtered(
            lambda line: not line.display_type and line.product_id == product
        )
        total_qty = sum(lines.mapped("product_qty"))
        if not lines or not total_qty:
            return 0.0
        return sum(
            line.product_qty * order._systore_line_cost_mxn(line)
            for line in lines
        ) / total_qty

    @api.model
    def _rebuild_snapshot(self, company, period):
        self.sudo().search([
            ("company_id", "=", company.id),
            ("movement_date", ">=", period["utc_start"]),
            ("movement_date", "<", period["utc_end"]),
        ]).unlink()
        move_lines = self.env["stock.move.line"].sudo().search([
            ("company_id", "=", company.id),
            ("state", "=", "done"),
            ("lot_id", "!=", False),
            ("location_dest_id.usage", "=", "customer"),
            ("date", ">=", period["utc_start"]),
            ("date", "<", period["utc_end"]),
        ])
        lot_names = list(set(move_lines.mapped("lot_id.name")))
        orders = self.env["purchase.order"].sudo().search([
            ("company_id", "=", company.id),
            ("name", "in", lot_names),
            ("state", "!=", "cancel"),
        ])
        orders_by_name = {order.name: order for order in orders}
        currency = company.currency_id
        values = []
        for move_line in move_lines:
            order = orders_by_name.get(move_line.lot_id.name)
            sale = self._sale_from_move_line(move_line)
            if not order or not sale:
                continue
            warehouse = sale.warehouse_id
            if not warehouse or not warehouse._systore_is_managed_for_supply():
                continue
            quantity = self._move_line_qty(move_line)
            if move_line.product_uom_id != move_line.product_id.uom_id:
                quantity = move_line.product_uom_id._compute_quantity(
                    quantity, move_line.product_id.uom_id
                )
            unit_cost = self._po_product_cost(order, move_line.product_id)
            picking = move_line.picking_id or move_line.move_id.picking_id
            values.append({
                "company_id": company.id,
                "currency_id": currency.id,
                "purchase_order_id": order.id,
                "sale_order_id": sale.id,
                "picking_id": picking.id if picking else False,
                "move_line_id": move_line.id,
                "lot_id": move_line.lot_id.id,
                "supplier_id": order.partner_id.id,
                "warehouse_id": warehouse.id,
                "channel": warehouse._systore_resolved_supply_channel(picking.location_id),
                "product_id": move_line.product_id.id,
                "sku": move_line.product_id.default_code or "",
                "quantity": quantity,
                "unit_cost_mxn": unit_cost,
                "total_cost_mxn": quantity * unit_cost,
                "movement_date": move_line.date,
            })
        for start in range(0, len(values), 1000):
            self.sudo().create(values[start:start + 1000])
        return len(values)
