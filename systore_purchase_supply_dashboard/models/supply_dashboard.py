from datetime import datetime, time
from collections import defaultdict

import pytz
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SystoreSupplyDashboard(models.AbstractModel):
    _name = "systore.supply.dashboard"
    _description = "Servicio del tablero de abastecimiento"

    @api.model
    def _historical_purchase_orders(self, company, warehouse_id=None, channel=None):
        """Confirmed purchases used by the current accounts-payable follow-up."""
        orders = self.env["purchase.order"].sudo().search([
            ("company_id", "=", company.id),
            ("state", "in", ["purchase", "done"]),
        ])
        if not warehouse_id and not channel:
            return orders
        return orders.filtered(lambda order: (
            order.picking_type_id.warehouse_id
            and (not warehouse_id or order.picking_type_id.warehouse_id.id == warehouse_id)
            and (
                not channel
                or order.picking_type_id.warehouse_id._systore_resolved_supply_channel(
                    order.picking_type_id.default_location_dest_id
                ) == channel
            )
        ))

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
        return {
            "period_month": period["key"],
            "purchases": purchases,
            "demand": demand,
            "trace": 0,
        }

    @api.model
    def get_dashboard_data(self, filters=None):
        filters = filters or {}
        period = self._month_period(filters.get("period_month"))
        company = self.env.company
        demand_domain = [
            ("company_id", "=", company.id),
            ("period_month", "=", period["month_start"]),
        ]
        channel = filters.get("channel")
        warehouse_id = filters.get("warehouse_id")
        supplier_id = filters.get("supplier_id")
        if channel:
            demand_domain.append(("channel", "=", channel))
        if warehouse_id:
            warehouse_id = int(warehouse_id)
            demand_domain.append(("warehouse_id", "=", warehouse_id))
        if supplier_id:
            supplier_id = int(supplier_id)
        DemandLine = self.env["systore.supply.demand.line"]
        demand_lines = DemandLine.search(demand_domain)
        sale_orders = demand_lines.mapped("sale_order_id")
        pickings = demand_lines.mapped("picking_id")

        kpis = {
            "sale_orders": len(sale_orders),
            "partial_pickings": len(pickings),
            "open_demand_qty": sum(demand_lines.mapped("open_demand_qty")),
            "ready_qty": sum(demand_lines.mapped("reserved_qty")),
            "missing_to_buy_qty": sum(demand_lines.mapped("missing_to_buy_qty")),
        }

        demand_rows = DemandLine.search_read(
            demand_domain,
            [
                "sale_order_id", "picking_id", "source_location_id", "scheduled_date",
                "warehouse_id", "channel", "product_id", "sku",
                "open_demand_qty", "reserved_qty",
                "missing_to_buy_qty", "coverage_status",
            ],
            order="scheduled_date, sale_order_id, sku",
            limit=100,
        )

        chart_data = self._get_chart_data(
            company,
            period,
            channel=channel,
            warehouse_id=warehouse_id,
            supplier_id=supplier_id,
        )

        warehouses = self.env["stock.warehouse"].search_read(
            [("company_id", "=", company.id)], ["name"], order="name"
        )
        historical_orders = self._historical_purchase_orders(
            company, warehouse_id=warehouse_id, channel=channel
        )
        suppliers = historical_orders.mapped("partner_id")
        for order in historical_orders:
            suppliers |= self.env["res.partner"].browse([
                component["partner"].id
                for component in order._systore_debt_components()
                if component.get("partner")
            ])
        supplier_options = [
            {"id": supplier.id, "name": supplier.display_name}
            for supplier in suppliers.sorted(lambda item: (item.display_name or "").lower())
        ]
        return {
            "period_month": period["key"],
            "kpis": kpis,
            "charts": chart_data["charts"],
            "purchases": [],
            "demand": demand_rows,
            "trace": [],
            "suppliers": supplier_options,
            "rankings": chart_data["rankings"],
            "warehouses": warehouses,
            "counts": {
                "purchase_lines": 0,
                "demand_lines": len(demand_lines),
                "trace_lines": 0,
            },
        }

    @api.model
    def _get_chart_data(self, company, period, channel=None, warehouse_id=None, supplier_id=None):
        """Build lightweight chart totals for the selected calendar month."""
        Picking = self.env["stock.picking"].sudo()
        pickings = Picking.search([
            ("company_id", "=", company.id),
            ("state", "!=", "cancel"),
            ("systore_batch_readiness_state", "in", ["complete", "partial"]),
            ("location_id.name", "=ilike", "Existencias"),
            ("scheduled_date", ">=", period["utc_start"]),
            ("scheduled_date", "<", period["utc_end"]),
        ])
        DemandLine = self.env["systore.supply.demand.line"]
        sale_metrics = {}
        for picking in pickings:
            sale = DemandLine._sale_from_picking(picking)
            if not sale:
                continue
            warehouse = sale.warehouse_id or picking.picking_type_id.warehouse_id
            if not warehouse or (warehouse_id and warehouse.id != warehouse_id):
                continue
            resolved_channel = warehouse._systore_resolved_supply_channel(picking.location_id)
            status = picking.systore_batch_readiness_state
            metrics = sale_metrics.setdefault(sale.id, {
                "status": status,
                "channel": resolved_channel,
                "pieces": 0.0,
            })
            if status == "partial":
                metrics["status"] = "partial"
            for move in picking.move_ids_without_package.filtered(
                lambda item: item.state != "cancel" and item.product_id
            ):
                metrics["pieces"] += DemandLine._convert_qty(
                    move.product_uom_qty or 0.0,
                    move.product_uom,
                    move.product_id,
                )

        status_counts = defaultdict(int)
        status_pieces = defaultdict(float)
        status_sale_ids = defaultdict(list)
        channel_counts = defaultdict(int)
        channel_pieces = defaultdict(float)
        channel_sale_ids = defaultdict(list)
        for sale_id, metrics in sale_metrics.items():
            status = metrics["status"]
            resolved_channel = metrics["channel"]
            channel_counts[resolved_channel] += 1
            channel_pieces[resolved_channel] += metrics["pieces"]
            channel_sale_ids[resolved_channel].append(sale_id)
            if not channel or resolved_channel == channel:
                status_counts[status] += 1
                status_pieces[status] += metrics["pieces"]
                status_sale_ids[status].append(sale_id)

        status_total = status_counts.get("complete", 0) + status_counts.get("partial", 0)
        readiness = [
            {
                "key": "complete",
                "label": "Listas",
                "value": status_counts.get("complete", 0),
                "pieces": status_pieces.get("complete", 0.0),
                "percent": status_counts.get("complete", 0) / status_total * 100.0 if status_total else 0.0,
                "sale_ids": status_sale_ids.get("complete", []),
            },
            {
                "key": "partial",
                "label": "Parciales",
                "value": status_counts.get("partial", 0),
                "pieces": status_pieces.get("partial", 0.0),
                "percent": status_counts.get("partial", 0) / status_total * 100.0 if status_total else 0.0,
                "sale_ids": status_sale_ids.get("partial", []),
            },
        ]

        channel_total = channel_counts.get("wholesale", 0) + channel_counts.get("retail", 0)
        wholesale_pct = channel_counts.get("wholesale", 0) / channel_total * 100.0 if channel_total else 0.0

        purchase_domain = [
            ("company_id", "=", company.id),
            ("report_date", ">=", period["month_start"]),
            ("report_date", "<", period["month_end"]),
        ]
        if warehouse_id:
            purchase_domain.append(("warehouse_id", "=", warehouse_id))
        if channel:
            purchase_domain.append(("channel", "=", channel))
        base_purchase_lines = self.env["systore.supply.purchase.line"].search(purchase_domain)
        purchase_lines = base_purchase_lines.filtered(
            lambda line: not supplier_id or line.supplier_id.id == supplier_id
        )
        received_qty = sum(purchase_lines.mapped("received_qty"))
        pending_qty = sum(purchase_lines.mapped("pending_qty"))
        pieces_total = received_qty + pending_qty
        received_pct = received_qty / pieces_total * 100.0 if pieces_total else 0.0

        products = defaultdict(lambda: {
            "order_ids": set(), "ordered": 0.0, "received": 0.0, "pending": 0.0,
        })
        suppliers = defaultdict(lambda: {
            "order_ids": set(), "debt_order_ids": set(),
            "ordered": 0.0, "received": 0.0, "pending": 0.0,
        })
        for line in purchase_lines:
            product = products[line.product_id.id]
            product.update({"name": line.product_id.display_name, "sku": line.sku or ""})
            product["order_ids"].add(line.purchase_order_id.id)
            product["ordered"] += line.ordered_qty
            product["received"] += line.received_qty
            product["pending"] += line.pending_qty

            supplier = suppliers[line.supplier_id.id]
            supplier["name"] = line.supplier_id.display_name
            supplier["order_ids"].add(line.purchase_order_id.id)
            supplier["ordered"] += line.ordered_qty
            supplier["received"] += line.received_qty
            supplier["pending"] += line.pending_qty

        purchase_orders = purchase_lines.mapped("purchase_order_id")
        debt_orders = self._historical_purchase_orders(
            company, warehouse_id=warehouse_id, channel=channel
        )
        debt_by_sector = {
            "national": defaultdict(lambda: {
                "mxn": 0.0, "usd": 0.0, "paid_mxn": 0.0, "paid_usd": 0.0,
                "order_ids": set(), "name": "",
            }),
            "international": defaultdict(lambda: {
                "mxn": 0.0, "usd": 0.0, "paid_mxn": 0.0, "paid_usd": 0.0,
                "order_ids": set(), "name": "",
            }),
        }
        for order in debt_orders:
            sector = order._systore_resolved_purchase_origin()
            for component in order._systore_debt_components():
                partner = component["partner"]
                if supplier_id and partner.id != supplier_id:
                    continue
                debt = debt_by_sector[sector][partner.id]
                debt["name"] = partner.display_name
                debt["mxn"] += component["pending_mxn"]
                debt["usd"] += component["pending_usd"]
                debt["paid_mxn"] += component.get("paid_mxn", 0.0)
                debt["paid_usd"] += component.get("paid_usd", 0.0)
                debt["order_ids"].add(order.id)

        def ranking_rows(grouped, limit=None):
            result = []
            sorted_values = sorted(
                grouped.items(), key=lambda item: item[1]["ordered"], reverse=True
            )
            if limit:
                sorted_values = sorted_values[:limit]
            for record_id, values in sorted_values:
                ordered = values["ordered"]
                received = values["received"]
                result.append({
                    "id": record_id,
                    "name": values.get("name") or "Sin nombre",
                    "sku": values.get("sku", ""),
                    "order_count": len(values["order_ids"]),
                    "ordered": ordered,
                    "received": received,
                    "pending": values["pending"],
                    "received_percent": min(received / ordered * 100.0, 100.0) if ordered else 0.0,
                    "order_ids": list(values["order_ids"]),
                    "debt_order_ids": list(values.get("debt_order_ids", set())),
                    "debt": values.get("debt", 0.0),
                    "debt_usd": values.get("debt_usd", 0.0),
                })
            return result

        product_rows = ranking_rows(products, limit=10)
        supplier_rows = ranking_rows(suppliers, limit=10)

        def debt_rows(sector):
            rows = [{
                "id": partner_id,
                "name": values["name"] or "Sin proveedor",
                "debt": values["mxn"],
                "debt_usd": values["usd"],
                "paid_mxn": values["paid_mxn"],
                "paid_usd": values["paid_usd"],
                "debt_order_ids": list(values["order_ids"]),
            } for partner_id, values in debt_by_sector[sector].items()
                if values["mxn"] > 0 or values["usd"] > 0]
            rows.sort(key=lambda row: (row["debt"], row["debt_usd"]), reverse=True)
            max_debt = max((row["debt"] for row in rows), default=0.0)
            for row in rows:
                row["debt_percent"] = (
                    row["debt"] / max_debt * 100.0 if max_debt else 100.0
                )
            return rows[:10]

        national_debts = debt_rows("national")
        international_debts = debt_rows("international")

        return {
            "charts": {
                "readiness": readiness,
                "readiness_total": status_total,
                "readiness_pieces": sum(status_pieces.values()),
                "channels": {
                    "total": channel_total,
                    "wholesale": channel_counts.get("wholesale", 0),
                    "retail": channel_counts.get("retail", 0),
                    "wholesale_percent": wholesale_pct,
                    "wholesale_pieces": channel_pieces.get("wholesale", 0.0),
                    "retail_pieces": channel_pieces.get("retail", 0.0),
                    "wholesale_sale_ids": channel_sale_ids.get("wholesale", []),
                    "retail_sale_ids": channel_sale_ids.get("retail", []),
                },
                "pieces": {
                    "total": pieces_total,
                    "received": received_qty,
                    "pending": pending_qty,
                    "received_percent": received_pct,
                    "purchase_order_ids": purchase_orders.ids,
                },
            },
            "rankings": {
                "products": product_rows,
                "suppliers": supplier_rows,
                "debts": national_debts + international_debts,
                "debts_national": national_debts,
                "debts_international": international_debts,
                "debt_national_mxn": sum(
                    value["mxn"] for value in debt_by_sector["national"].values()
                ),
                "debt_international_mxn": sum(
                    value["mxn"] for value in debt_by_sector["international"].values()
                ),
                "debt_international_usd": sum(
                    value["usd"] for value in debt_by_sector["international"].values()
                ),
            },
        }
