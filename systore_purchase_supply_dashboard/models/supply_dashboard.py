from datetime import datetime, time

import pytz
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SystoreSupplyDashboard(models.AbstractModel):
    _name = "systore.supply.dashboard"
    _description = "Servicio del tablero de abastecimiento"

    @api.model
    def _month_period(self, period_month=None):
        """Return one strict calendar month using the user's timezone."""
        if not period_month:
            period_start = fields.Date.context_today(self).replace(day=1)
        else:
            try:
                period_start = datetime.strptime(period_month, "%Y-%m").date()
            except (TypeError, ValueError) as error:
                raise UserError(_("Selecciona un mes válido antes de actualizar.")) from error
        period_end = period_start + relativedelta(months=1)
        timezone = pytz.timezone(self.env.user.tz or "UTC")
        local_start = timezone.localize(datetime.combine(period_start, time.min))
        local_end = timezone.localize(datetime.combine(period_end, time.min))
        utc_start = local_start.astimezone(pytz.UTC).replace(tzinfo=None)
        utc_end = local_end.astimezone(pytz.UTC).replace(tzinfo=None)
        return {
            "key": period_start.strftime("%Y-%m"),
            "month_start": period_start,
            "month_end": period_end,
            "utc_start": fields.Datetime.to_string(utc_start),
            "utc_end": fields.Datetime.to_string(utc_end),
        }

    @api.model
    def action_refresh(self, period_month=None):
        company = self.env.company
        period = self._month_period(period_month)
        with self.env.cr.savepoint():
            purchases = self.env["systore.supply.purchase.line"]._rebuild_snapshot(company, period)
            demand = self.env["systore.supply.demand.line"]._rebuild_snapshot(company, period)
            trace = self.env["systore.supply.trace.line"]._rebuild_snapshot(company, period)
        return {
            "period_month": period["key"],
            "purchases": purchases,
            "demand": demand,
            "trace": trace,
        }

    @api.model
    def get_dashboard_data(self, filters=None):
        filters = filters or {}
        period = self._month_period(filters.get("period_month"))
        company = self.env.company
        purchase_domain = [
            ("company_id", "=", company.id),
            ("report_date", ">=", period["month_start"]),
            ("report_date", "<", period["month_end"]),
        ]
        demand_domain = [
            ("company_id", "=", company.id),
            ("period_month", "=", period["month_start"]),
        ]
        trace_domain = [
            ("company_id", "=", company.id),
            ("movement_date", ">=", period["utc_start"]),
            ("movement_date", "<", period["utc_end"]),
        ]

        channel = filters.get("channel")
        warehouse_id = filters.get("warehouse_id")
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
            "period_month": period["key"],
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
