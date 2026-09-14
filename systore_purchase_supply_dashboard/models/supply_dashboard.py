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

        warehouses = self.env["stock.warehouse"].search_read(
            [("company_id", "=", company.id)], ["name"], order="name"
        )
        return {
            "period_month": period["key"],
            "kpis": kpis,
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
