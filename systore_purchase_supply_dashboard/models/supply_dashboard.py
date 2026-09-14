from odoo import api, models


class SystoreSupplyDashboard(models.AbstractModel):
    _name = "systore.supply.dashboard"
    _description = "Servicio del tablero de abastecimiento"

    @api.model
    def action_refresh(self):
        company = self.env.company
        with self.env.cr.savepoint():
            purchases = self.env["systore.supply.purchase.line"]._rebuild_snapshot(company)
            demand = self.env["systore.supply.demand.line"]._rebuild_snapshot(company)
            trace = self.env["systore.supply.trace.line"]._rebuild_snapshot(company)
        return {
            "purchases": purchases,
            "demand": demand,
            "trace": trace,
        }

    @api.model
    def get_dashboard_data(self, filters=None):
        filters = filters or {}
        company = self.env.company
        purchase_domain = [("company_id", "=", company.id)]
        demand_domain = [("company_id", "=", company.id)]
        trace_domain = [("company_id", "=", company.id)]

        date_from = filters.get("date_from")
        date_to = filters.get("date_to")
        channel = filters.get("channel")
        warehouse_id = filters.get("warehouse_id")
        if date_from:
            purchase_domain.append(("report_date", ">=", date_from))
            trace_domain.append(("movement_date", ">=", f"{date_from} 00:00:00"))
        if date_to:
            purchase_domain.append(("report_date", "<=", date_to))
            trace_domain.append(("movement_date", "<=", f"{date_to} 23:59:59"))
        if channel:
            purchase_domain.append(("channel", "=", channel))
            demand_domain.append(("channel", "=", channel))
            trace_domain.append(("channel", "=", channel))
        if warehouse_id:
            warehouse_id = int(warehouse_id)
            purchase_domain.append(("warehouse_id", "=", warehouse_id))
            demand_domain.append(("warehouse_id", "=", warehouse_id))
            trace_domain.append(("warehouse_id", "=", warehouse_id))

        PurchaseLine = self.env["systore.supply.purchase.line"]
        DemandLine = self.env["systore.supply.demand.line"]
        TraceLine = self.env["systore.supply.trace.line"]

        purchase_lines = PurchaseLine.search(purchase_domain)
        demand_lines = DemandLine.search(demand_domain)
        trace_lines = TraceLine.search(trace_domain)
        purchase_orders = purchase_lines.mapped("purchase_order_id")

        kpis = {
            "purchase_orders": len(purchase_orders),
            "ordered_qty": sum(purchase_lines.mapped("ordered_qty")),
            "received_qty": sum(purchase_lines.mapped("received_qty")),
            "pending_receipt_qty": sum(purchase_lines.mapped("pending_qty")),
            "received_value_mxn": sum(purchase_lines.mapped("received_value_mxn")),
            "pending_value_mxn": sum(purchase_lines.mapped("pending_value_mxn")),
            "open_demand_qty": sum(demand_lines.mapped("open_demand_qty")),
            "missing_to_buy_qty": sum(demand_lines.mapped("missing_to_buy_qty")),
            "amount_payable_mxn": sum(purchase_orders.mapped("systore_amount_payable_mxn")),
            "amount_paid_mxn": sum(purchase_orders.mapped("systore_amount_paid_mxn")),
            "amount_pending_mxn": sum(purchase_orders.mapped("systore_amount_pending_mxn")),
        }

        purchase_rows = PurchaseLine.search_read(
            purchase_domain,
            [
                "purchase_order_id", "supplier_id", "warehouse_id", "channel",
                "product_id", "sku", "purchase_origin", "first_receipt_date",
                "ordered_qty", "received_qty", "pending_qty", "reception_percent",
                "landed_cost_mxn_unit", "received_value_mxn", "pending_value_mxn",
                "payment_status",
            ],
            order="report_date desc, purchase_order_name desc",
            limit=60,
        )
        demand_rows = DemandLine.search_read(
            demand_domain,
            [
                "warehouse_id", "channel", "product_id", "sku", "sales_order_count",
                "linked_wholesale_sale_count", "unlinked_wholesale_sale_count",
                "complete_picking_count", "partial_picking_count",
                "open_demand_qty", "on_hand_qty", "reserved_qty", "incoming_qty",
                "missing_to_buy_qty", "coverage_status",
            ],
            order="missing_to_buy_qty desc, open_demand_qty desc",
            limit=60,
        )
        trace_rows = TraceLine.search_read(
            trace_domain,
            [
                "purchase_order_id", "sale_order_id", "lot_id", "supplier_id",
                "warehouse_id", "channel", "product_id", "sku", "quantity",
                "unit_cost_mxn", "total_cost_mxn", "movement_date",
            ],
            order="movement_date desc",
            limit=60,
        )

        supplier_groups = PurchaseLine.read_group(
            purchase_domain,
            ["supplier_id", "ordered_value_mxn:sum", "received_value_mxn:sum", "pending_value_mxn:sum"],
            ["supplier_id"],
        )
        supplier_groups = sorted(
            supplier_groups,
            key=lambda group: group.get("ordered_value_mxn", 0.0),
            reverse=True,
        )[:10]
        suppliers = []
        for group in supplier_groups:
            supplier = group.get("supplier_id")
            supplier_orders = purchase_orders.filtered(
                lambda order: supplier and order.partner_id.id == supplier[0]
            )
            suppliers.append({
                "supplier_id": supplier,
                "ordered_value_mxn": group.get("ordered_value_mxn", 0.0),
                "received_value_mxn": group.get("received_value_mxn", 0.0),
                "pending_value_mxn": group.get("pending_value_mxn", 0.0),
                "amount_pending_mxn": sum(supplier_orders.mapped("systore_amount_pending_mxn")),
            })

        warehouses = self.env["stock.warehouse"].search_read(
            [("company_id", "=", company.id)], ["name"], order="name"
        )
        return {
            "kpis": kpis,
            "purchases": purchase_rows,
            "demand": demand_rows,
            "trace": trace_rows,
            "suppliers": suppliers,
            "warehouses": warehouses,
            "counts": {
                "purchase_lines": len(purchase_lines),
                "demand_lines": len(demand_lines),
                "trace_lines": len(trace_lines),
            },
        }
