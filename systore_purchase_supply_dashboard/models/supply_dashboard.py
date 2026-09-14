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
        if channel:
            demand_domain.append(("channel", "=", channel))
        if warehouse_id:
            warehouse_id = int(warehouse_id)
            demand_domain.append(("warehouse_id", "=", warehouse_id))
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
        )

        warehouses = self.env["stock.warehouse"].search_read(
            [("company_id", "=", company.id)], ["name"], order="name"
        )
        return {
            "period_month": period["key"],
            "kpis": kpis,
            "charts": chart_data,
            "purchases": [],
            "demand": demand_rows,
            "trace": [],
            "suppliers": [],
            "warehouses": warehouses,
            "counts": {
                "purchase_lines": 0,
                "demand_lines": len(demand_lines),
                "trace_lines": 0,
            },
        }

    @api.model
    def _get_chart_data(self, company, period, channel=None, warehouse_id=None):
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
        sale_status = {}
        sale_channel = {}
        for picking in pickings:
            sale = DemandLine._sale_from_picking(picking)
            if not sale:
                continue
            warehouse = sale.warehouse_id or picking.picking_type_id.warehouse_id
            if not warehouse or (warehouse_id and warehouse.id != warehouse_id):
                continue
            resolved_channel = warehouse._systore_resolved_supply_channel(picking.location_id)
            sale_channel[sale.id] = resolved_channel
            status = picking.systore_batch_readiness_state
            if status == "partial" or sale.id not in sale_status:
                sale_status[sale.id] = status

        status_counts = defaultdict(int)
        channel_counts = defaultdict(int)
        for sale_id, status in sale_status.items():
            resolved_channel = sale_channel.get(sale_id, "retail")
            channel_counts[resolved_channel] += 1
            if not channel or resolved_channel == channel:
                status_counts[status] += 1

        max_status = max(status_counts.get("complete", 0), status_counts.get("partial", 0), 1)
        readiness = [
            {
                "key": "complete",
                "label": "Listas",
                "value": status_counts.get("complete", 0),
                "height": status_counts.get("complete", 0) / max_status * 100.0,
            },
            {
                "key": "partial",
                "label": "Parciales",
                "value": status_counts.get("partial", 0),
                "height": status_counts.get("partial", 0) / max_status * 100.0,
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
        purchase_lines = self.env["systore.supply.purchase.line"].search(purchase_domain)
        received_qty = sum(purchase_lines.mapped("received_qty"))
        pending_qty = sum(purchase_lines.mapped("pending_qty"))
        pieces_total = received_qty + pending_qty
        received_pct = received_qty / pieces_total * 100.0 if pieces_total else 0.0

        return {
            "readiness": readiness,
            "channels": {
                "total": channel_total,
                "wholesale": channel_counts.get("wholesale", 0),
                "retail": channel_counts.get("retail", 0),
                "wholesale_percent": wholesale_pct,
            },
            "pieces": {
                "total": pieces_total,
                "received": received_qty,
                "pending": pending_qty,
                "received_percent": received_pct,
            },
        }
