from collections import defaultdict

from odoo import api, fields, models


CHANNEL_SELECTION = [
    ("wholesale", "Mayoreo"),
    ("marketplace", "Marketplace"),
    ("other", "Otro"),
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
    received_qty = fields.Float(string="Piezas recibidas", readonly=True)
    pending_qty = fields.Float(string="Piezas pendientes", readonly=True)
    overreceived_qty = fields.Float(string="Excedente recibido", readonly=True)
    reception_percent = fields.Float(string="% recepción", readonly=True, group_operator="avg")

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
    amount_payable_mxn = fields.Monetary(string="Total a pagar MXN", currency_field="currency_id", readonly=True)
    amount_paid_mxn = fields.Monetary(string="Pagado MXN", currency_field="currency_id", readonly=True)
    amount_pending_mxn = fields.Monetary(string="Saldo pendiente MXN", currency_field="currency_id", readonly=True)

    @api.model
    def _first_receipt_date(self, order):
        moves = order.order_line.move_ids.filtered(
            lambda move: move.state == "done" and move.location_id.usage == "supplier"
        )
        if not moves:
            moves = self.env["stock.move"].search([
                ("picking_id.origin", "=", order.name),
                ("company_id", "=", order.company_id.id),
                ("state", "=", "done"),
                ("location_id.usage", "=", "supplier"),
            ])
        dates = [
            move.picking_id.date_done or move.date
            for move in moves
            if move.picking_id.date_done or move.date
        ]
        return min(dates) if dates else False

    @api.model
    def _rebuild_snapshot(self, company):
        self.sudo().search([("company_id", "=", company.id)]).unlink()
        orders = self.env["purchase.order"].sudo().search([
            ("company_id", "=", company.id),
            ("state", "in", ["purchase", "done"]),
        ])
        values = []
        currency = company.currency_id
        for order in orders:
            first_receipt = self._first_receipt_date(order)
            report_date = fields.Date.to_date(first_receipt or order.date_order)
            warehouse = order.picking_type_id.warehouse_id
            channel = warehouse._systore_resolved_supply_channel() if warehouse else "other"
            purchase_origin = order._systore_resolved_purchase_origin()
            for line in order.order_line.filtered(lambda item: not item.display_type and item.product_id):
                ordered = line.product_qty or 0.0
                received = line.qty_received or 0.0
                pending = max(ordered - received, 0.0)
                overreceived = max(received - ordered, 0.0)
                landed_cost = order._systore_line_cost_mxn(line)
                reception_percent = (received / ordered * 100.0) if ordered else 0.0
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
                    "has_receipt": bool(first_receipt),
                    "ordered_qty": ordered,
                    "received_qty": received,
                    "pending_qty": pending,
                    "overreceived_qty": overreceived,
                    "reception_percent": reception_percent,
                    "gross_usd_unit": line.x_gross_usd or 0.0,
                    "shipping_usd_unit": line.x_ship_usd or 0.0,
                    "gross_mxn_unit": line.x_gross_mxn or 0.0,
                    "shipping_mxn_unit": line.x_ship_mxn or 0.0,
                    "import_mxn_unit": line.x_import_mxn or 0.0,
                    "landed_cost_mxn_unit": landed_cost,
                    "merchandise_usd_total": ordered * (line.x_gross_usd or 0.0),
                    "shipping_usd_total": ordered * (line.x_ship_usd or 0.0),
                    "ordered_value_mxn": ordered * landed_cost,
                    "received_value_mxn": received * landed_cost,
                    "pending_value_mxn": pending * landed_cost,
                    "payment_status": order.systore_payment_status,
                    "amount_payable_mxn": order.systore_amount_payable_mxn,
                    "amount_paid_mxn": order.systore_amount_paid_mxn,
                    "amount_pending_mxn": order.systore_amount_pending_mxn,
                })
        for start in range(0, len(values), 1000):
            self.sudo().create(values[start:start + 1000])
        return len(values)


class SystoreSupplyDemandLine(models.Model):
    _name = "systore.supply.demand.line"
    _description = "Demanda y necesidad de compra"
    _order = "missing_to_buy_qty desc, warehouse_id, sku"

    company_id = fields.Many2one("res.company", required=True, index=True, readonly=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="Almacén", required=True, index=True, readonly=True)
    channel = fields.Selection(CHANNEL_SELECTION, string="Canal", required=True, index=True, readonly=True)
    product_id = fields.Many2one("product.product", string="Producto", required=True, index=True, readonly=True)
    sku = fields.Char(string="SKU", index=True, readonly=True)
    sales_order_count = fields.Integer(string="Ventas abiertas", readonly=True)
    linked_wholesale_sale_count = fields.Integer(string="Ventas Mayoreo con OC", readonly=True)
    unlinked_wholesale_sale_count = fields.Integer(string="Ventas Mayoreo sin OC", readonly=True)
    complete_picking_count = fields.Integer(string="Traslados completos", readonly=True)
    partial_picking_count = fields.Integer(string="Traslados parciales", readonly=True)
    open_demand_qty = fields.Float(string="Demanda pendiente", readonly=True)
    on_hand_qty = fields.Float(string="Existencia física", readonly=True)
    reserved_qty = fields.Float(string="Existencia reservada", readonly=True)
    free_qty = fields.Float(string="Existencia libre", readonly=True)
    incoming_qty = fields.Float(string="Comprado por recibir", readonly=True)
    covered_by_stock_qty = fields.Float(string="Cubierto por existencia", readonly=True)
    covered_by_incoming_qty = fields.Float(string="Cubierto por compras", readonly=True)
    missing_to_buy_qty = fields.Float(string="Pendiente de comprar", readonly=True)
    coverage_status = fields.Selection(
        [
            ("stock", "Cubierta con existencia"),
            ("incoming", "Cubierta con compras"),
            ("shortage", "Falta comprar"),
            ("no_demand", "Sin demanda pendiente"),
        ],
        string="Cobertura",
        index=True,
        readonly=True,
    )
    snapshot_date = fields.Datetime(string="Actualizado", readonly=True)

    @api.model
    def _convert_qty(self, qty, source_uom, product):
        if source_uom and source_uom != product.uom_id:
            return source_uom._compute_quantity(qty, product.uom_id)
        return qty

    @api.model
    def _warehouse_stock(self, warehouse, product):
        location = warehouse.lot_stock_id
        on_hand = product.with_context(location=location.id).qty_available
        groups = self.env["stock.quant"].sudo().read_group(
            [
                ("product_id", "=", product.id),
                ("location_id", "child_of", location.id),
            ],
            ["reserved_quantity:sum"],
            [],
        )
        reserved = groups[0].get("reserved_quantity", 0.0) if groups else 0.0
        return on_hand, reserved

    @api.model
    def _rebuild_snapshot(self, company):
        self.sudo().search([("company_id", "=", company.id)]).unlink()
        buckets = defaultdict(lambda: {
            "demand": 0.0,
            "incoming": 0.0,
            "sales": set(),
            "linked_sales": set(),
            "unlinked_sales": set(),
            "complete_pickings": set(),
            "partial_pickings": set(),
        })

        sale_lines = self.env["sale.order.line"].sudo().search([
            ("company_id", "=", company.id),
            ("state", "in", ["sale", "done"]),
            ("display_type", "=", False),
            ("product_id", "!=", False),
        ])
        for line in sale_lines:
            warehouse = line.order_id.warehouse_id
            if not warehouse or line.product_id.type == "service":
                continue
            pending = max((line.product_uom_qty or 0.0) - (line.qty_delivered or 0.0), 0.0)
            pending = self._convert_qty(pending, line.product_uom, line.product_id)
            key = (warehouse.id, line.product_id.id)
            buckets[key]["demand"] += pending
            if pending:
                buckets[key]["sales"].add(line.order_id.id)
                if warehouse.is_wholesale:
                    if line.order_id.associated_purchase_order_ids:
                        buckets[key]["linked_sales"].add(line.order_id.id)
                    else:
                        buckets[key]["unlinked_sales"].add(line.order_id.id)

        Picking = self.env["stock.picking"].sudo()
        if "systore_batch_readiness_state" in Picking._fields:
            pickings = Picking.search([
                ("company_id", "=", company.id),
                ("state", "not in", ["done", "cancel"]),
            ])
            for picking in pickings:
                sale = picking.sale_id if "sale_id" in picking._fields else False
                warehouse = sale.warehouse_id if sale else picking.picking_type_id.warehouse_id
                if not warehouse:
                    continue
                for product in picking.move_ids_without_package.filtered(
                    lambda move: move.state not in ("done", "cancel") and move.product_id
                ).mapped("product_id"):
                    key = (warehouse.id, product.id)
                    if picking.systore_batch_readiness_state == "partial":
                        buckets[key]["partial_pickings"].add(picking.id)
                    else:
                        buckets[key]["complete_pickings"].add(picking.id)

        purchase_lines = self.env["purchase.order.line"].sudo().search([
            ("company_id", "=", company.id),
            ("order_id.state", "in", ["purchase", "done"]),
            ("display_type", "=", False),
            ("product_id", "!=", False),
        ])
        for line in purchase_lines:
            warehouse = line.order_id.picking_type_id.warehouse_id
            if not warehouse or line.product_id.type == "service":
                continue
            pending = max((line.product_qty or 0.0) - (line.qty_received or 0.0), 0.0)
            pending = self._convert_qty(pending, line.product_uom, line.product_id)
            buckets[(warehouse.id, line.product_id.id)]["incoming"] += pending

        now = fields.Datetime.now()
        values = []
        Warehouse = self.env["stock.warehouse"].sudo()
        Product = self.env["product.product"].sudo()
        for (warehouse_id, product_id), bucket in buckets.items():
            warehouse = Warehouse.browse(warehouse_id)
            product = Product.browse(product_id)
            demand = bucket["demand"]
            incoming = bucket["incoming"]
            on_hand, reserved = self._warehouse_stock(warehouse, product)
            free = max(on_hand - reserved, 0.0)
            covered_stock = min(demand, max(on_hand, 0.0))
            uncovered = max(demand - covered_stock, 0.0)
            covered_incoming = min(uncovered, incoming)
            missing = max(uncovered - incoming, 0.0)
            if demand <= 0:
                status = "no_demand"
            elif missing > 0:
                status = "shortage"
            elif demand <= max(on_hand, 0.0):
                status = "stock"
            else:
                status = "incoming"
            values.append({
                "company_id": company.id,
                "warehouse_id": warehouse.id,
                "channel": warehouse._systore_resolved_supply_channel(),
                "product_id": product.id,
                "sku": product.default_code or "",
                "sales_order_count": len(bucket["sales"]),
                "linked_wholesale_sale_count": len(bucket["linked_sales"]),
                "unlinked_wholesale_sale_count": len(bucket["unlinked_sales"]),
                "complete_picking_count": len(bucket["complete_pickings"]),
                "partial_picking_count": len(bucket["partial_pickings"]),
                "open_demand_qty": demand,
                "on_hand_qty": on_hand,
                "reserved_qty": reserved,
                "free_qty": free,
                "incoming_qty": incoming,
                "covered_by_stock_qty": covered_stock,
                "covered_by_incoming_qty": covered_incoming,
                "missing_to_buy_qty": missing,
                "coverage_status": status,
                "snapshot_date": now,
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
    def _rebuild_snapshot(self, company):
        self.sudo().search([("company_id", "=", company.id)]).unlink()
        move_lines = self.env["stock.move.line"].sudo().search([
            ("company_id", "=", company.id),
            ("state", "=", "done"),
            ("lot_id", "!=", False),
            ("location_dest_id.usage", "=", "customer"),
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
                "warehouse_id": warehouse.id if warehouse else False,
                "channel": warehouse._systore_resolved_supply_channel() if warehouse else "other",
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
