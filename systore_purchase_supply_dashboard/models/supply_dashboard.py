from datetime import datetime, time, timedelta
from collections import defaultdict

import pytz
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class SystoreSupplyDashboard(models.AbstractModel):
    _name = "systore.supply.dashboard"
    _description = "Servicio de Analítica de compras"

    def _check_systore_supply_access(self):
        if not (
            self.env.user.has_group(
                "systore_purchase_supply_dashboard.group_supply_dashboard_user"
            )
            or self.env.user.has_group("base.group_system")
        ):
            raise AccessError(_(
                "No tienes acceso al módulo Analítica de compras. "
                "Solicita que te agreguen desde Configuración."
            ))

    @api.model
    def _historical_purchase_orders(
        self, company, warehouse_id=None, channel=None, supplier_type=None
    ):
        """Confirmed purchases used by the current accounts-payable follow-up."""
        orders = self.env["purchase.order"].sudo().search([
            ("company_id", "=", company.id),
            ("state", "in", ["purchase", "done"]),
        ])
        return orders.filtered(lambda order: (
            order.picking_type_id.warehouse_id
            and order.picking_type_id.warehouse_id._systore_is_managed_for_supply()
            and (not warehouse_id or order.picking_type_id.warehouse_id.id == warehouse_id)
            and (
                not channel
                or order.picking_type_id.warehouse_id._systore_resolved_supply_channel(
                    order.picking_type_id.default_location_dest_id
                ) == channel
            )
            and (
                not supplier_type
                or order._systore_resolved_purchase_origin() == supplier_type
            )
        ))

    @api.model
    def _supplier_credit_rows(
        self, company, supplier_id=None, supplier_type=None
    ):
        """Return the supplier credit position independently from the month filter."""
        credit_orders = self._historical_purchase_orders(
            company, supplier_type=supplier_type
        ).filtered(lambda order: (
            order.systore_purchase_condition == "credit"
            and (not supplier_id or order.partner_id.id == supplier_id)
        ))
        partners = credit_orders.mapped("partner_id")
        if not supplier_type:
            configured_domain = [
                ("systore_supplier_credit_enabled", "=", True),
                ("supplier_rank", ">", 0),
            ]
            if supplier_id:
                configured_domain.append(("id", "=", supplier_id))
            partners |= self.env["res.partner"].sudo().search(configured_domain)

        rows = []
        for partner in partners:
            partner_orders = credit_orders.filtered(lambda order: order.partner_id == partner)
            currency = (
                partner.systore_supplier_credit_currency_id
                or (partner_orders[:1].systore_credit_currency_id if partner_orders else False)
                or company.currency_id
            )
            used = 0.0
            for order in partner_orders:
                used += order._systore_credit_balance_in_currency(currency)

            limit_amount = partner.systore_supplier_credit_limit or 0.0
            available = limit_amount - used
            utilization = (
                used / limit_amount * 100.0
                if limit_amount else (100.0 if used else 0.0)
            )
            rows.append({
                "id": partner.id,
                "name": partner.display_name,
                "currency": currency.name,
                "currency_symbol": currency.symbol or currency.name,
                "limit": limit_amount,
                "used": used,
                "available": available,
                "excess": max(-available, 0.0),
                "utilization": utilization,
                "utilization_bar": min(max(utilization, 0.0), 100.0),
                "order_count": len(partner_orders),
                "order_ids": partner_orders.ids,
            })
        rows.sort(
            key=lambda row: (row["utilization"], row["used"]),
            reverse=True,
        )
        return rows

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
    def _receipt_date_period(self, date_from=None, date_to=None, fallback=None):
        fallback = fallback or self._month_period()
        try:
            start_date = (
                datetime.strptime(date_from, "%Y-%m-%d").date()
                if date_from else fallback["month_start"]
            )
            end_date = (
                datetime.strptime(date_to, "%Y-%m-%d").date()
                if date_to else fallback["month_end"] - timedelta(days=1)
            )
        except (TypeError, ValueError) as error:
            raise UserError(_("Selecciona un rango de fechas válido.")) from error
        if start_date > end_date:
            raise UserError(_("La fecha inicial no puede ser posterior a la fecha final."))
        timezone = pytz.timezone(self.env.user.tz or "UTC")
        local_start = timezone.localize(datetime.combine(start_date, time.min))
        local_end = timezone.localize(datetime.combine(end_date + timedelta(days=1), time.min))
        return {
            "date_from": fields.Date.to_string(start_date),
            "date_to": fields.Date.to_string(end_date),
            "utc_start": fields.Datetime.to_string(
                local_start.astimezone(pytz.UTC).replace(tzinfo=None)
            ),
            "utc_end": fields.Datetime.to_string(
                local_end.astimezone(pytz.UTC).replace(tzinfo=None)
            ),
        }

    @api.model
    def action_refresh(self, period_month=None):
        self._check_systore_supply_access()
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
        self._check_systore_supply_access()
        filters = filters or {}
        period = self._month_period(filters.get("period_month"))
        receipt_period = self._receipt_date_period(
            filters.get("date_from"), filters.get("date_to"), fallback=period
        )
        company = self.env.company
        demand_domain = [
            ("company_id", "=", company.id),
            ("warehouse_id.systore_supply_management", "!=", "excluded"),
            ("picking_id.state", "not in", ["done", "cancel"]),
            ("picking_id.systore_batch_readiness_state", "=", "partial"),
        ]
        demand_period = filters.get("demand_period") or "all"
        if demand_period != "all":
            try:
                datetime.strptime(demand_period, "%Y-%m")
            except (TypeError, ValueError) as error:
                raise UserError(_("Selecciona un periodo de demanda válido.")) from error
        channel = filters.get("channel")
        warehouse_id = filters.get("warehouse_id")
        supplier_id = filters.get("supplier_id")
        supplier_type = filters.get("supplier_type")
        raw_product_ids = filters.get("product_ids") or []
        if not isinstance(raw_product_ids, (list, tuple, set)):
            raw_product_ids = [raw_product_ids]
        product_ids = []
        for value in raw_product_ids:
            try:
                product_id = int(value)
            except (TypeError, ValueError):
                continue
            if product_id > 0:
                product_ids.append(product_id)
        product_ids = list(dict.fromkeys(product_ids))
        if supplier_type not in ("national", "international"):
            supplier_type = None
        if channel:
            demand_domain.append(("channel", "=", channel))
        if warehouse_id:
            warehouse_id = int(warehouse_id)
            demand_domain.append(("warehouse_id", "=", warehouse_id))
        if supplier_id:
            supplier_id = int(supplier_id)
        DemandLine = self.env["systore.supply.demand.line"]
        available_period_lines = DemandLine.search(demand_domain)
        available_demand_months = sorted({
            fields.Date.to_string(line.period_month)[:7]
            for line in available_period_lines
            if line.period_month
        }, reverse=True)
        if demand_period != "all" and demand_period not in available_demand_months:
            available_demand_months.append(demand_period)
            available_demand_months.sort(reverse=True)

        scoped_demand_domain = list(demand_domain)
        if demand_period != "all":
            scoped_demand_domain.append(
                ("period_month", "<=", fields.Date.to_date(f"{demand_period}-01"))
            )
        product_option_lines = DemandLine.search(scoped_demand_domain)
        product_options = [{
            "id": product.id,
            "name": product.display_name,
            "sku": product.default_code or "",
        } for product in sorted(
            product_option_lines.mapped("product_id"),
            key=lambda item: ((item.default_code or "").lower(), (item.display_name or "").lower()),
        )]
        if product_ids:
            scoped_demand_domain.append(("product_id", "in", product_ids))
        candidate_demand_lines = DemandLine.search(scoped_demand_domain)
        latest_line_by_operation_product = {}
        for line in candidate_demand_lines:
            key = (line.picking_id.id, line.product_id.id)
            previous = latest_line_by_operation_product.get(key)
            if not previous or (
                line.snapshot_date or line.create_date or datetime.min
            ) > (
                previous.snapshot_date or previous.create_date or datetime.min
            ):
                latest_line_by_operation_product[key] = line
        all_demand_lines = DemandLine.browse(
            [line.id for line in latest_line_by_operation_product.values()]
        )

        waiting_order_ids = {"wholesale": set(), "retail": set()}
        waiting_pieces = defaultdict(float)
        for line in all_demand_lines:
            if line.open_demand_qty <= 0:
                continue
            line_channel = line.channel if line.channel in waiting_order_ids else "retail"
            if line.sale_order_id:
                waiting_order_ids[line_channel].add(line.sale_order_id.id)
            waiting_pieces[line_channel] += line.open_demand_qty
        waiting_counts = {
            key: len(order_ids) for key, order_ids in waiting_order_ids.items()
        }
        waiting_total_orders = sum(waiting_counts.values())
        waiting_total_pieces = sum(waiting_pieces.values())

        demand_by_product_month = defaultdict(lambda: {
            "open": 0.0, "ready": 0.0, "missing": 0.0,
            "warehouse_names": set(), "channels": set(),
        })
        for line in all_demand_lines:
            if not line.period_month:
                continue
            month_key = fields.Date.to_string(line.period_month)[:7]
            values = demand_by_product_month[(line.product_id.id, month_key)]
            values["name"] = line.product_id.display_name
            values["sku"] = line.sku or ""
            values["open"] += line.open_demand_qty
            values["ready"] += line.reserved_qty
            values["missing"] += line.missing_to_buy_qty
            values["warehouse_names"].add(line.warehouse_id.display_name)
            values["channels"].add(line.channel)

        incoming_by_product = defaultdict(float)
        demand_product_ids = {key[0] for key in demand_by_product_month}
        if demand_product_ids:
            purchase_lines = self.env["purchase.order.line"].sudo().search([
                ("order_id.company_id", "=", company.id),
                ("order_id.state", "in", ["purchase", "done"]),
                ("product_id", "in", list(demand_product_ids)),
            ])
            PurchaseSnapshot = self.env["systore.supply.purchase.line"]
            for purchase_line in purchase_lines:
                order = purchase_line.order_id
                purchase_warehouse = order.picking_type_id.warehouse_id
                if (
                    not purchase_warehouse
                    or not purchase_warehouse._systore_is_managed_for_supply()
                ):
                    continue
                if warehouse_id and (
                    purchase_warehouse.id != warehouse_id
                ):
                    continue
                purchase_channel = (
                    purchase_warehouse._systore_resolved_supply_channel(
                        order.picking_type_id.default_location_dest_id
                    )
                )
                if channel and purchase_channel != channel:
                    continue
                _, _, received_net, _ = PurchaseSnapshot._line_receipt_quantities(
                    purchase_line
                )
                incoming = max((purchase_line.product_qty or 0.0) - received_net, 0.0)
                if (
                    purchase_line.product_uom
                    and purchase_line.product_id.uom_id
                    and purchase_line.product_uom != purchase_line.product_id.uom_id
                ):
                    incoming = purchase_line.product_uom._compute_quantity(
                        incoming, purchase_line.product_id.uom_id
                    )
                incoming_by_product[purchase_line.product_id.id] += incoming

        allocated_by_product_month = {}
        for product_id in demand_product_ids:
            remaining_incoming = incoming_by_product.get(product_id, 0.0)
            product_months = sorted(
                month_key for candidate_id, month_key in demand_by_product_month
                if candidate_id == product_id
            )
            for month_key in product_months:
                values = demand_by_product_month[(product_id, month_key)]
                applied_incoming = min(values["missing"], remaining_incoming)
                remaining_incoming -= applied_incoming
                allocated_by_product_month[(product_id, month_key)] = {
                    **values,
                    "incoming": applied_incoming,
                    "net_missing": max(values["missing"] - applied_incoming, 0.0),
                }

        selected_allocations = allocated_by_product_month
        demand_by_product = defaultdict(lambda: {
            "open": 0.0, "ready": 0.0, "missing": 0.0,
            "incoming": 0.0, "net_missing": 0.0,
            "warehouse_names": set(), "channels": set(), "months": set(),
        })
        for (product_id, month_key), values in selected_allocations.items():
            product = demand_by_product[product_id]
            for field_name in ("name", "sku"):
                product[field_name] = values[field_name]
            for field_name in ("open", "ready", "missing", "incoming", "net_missing"):
                product[field_name] += values[field_name]
            for field_name in ("warehouse_names", "channels"):
                product[field_name].update(values[field_name])
            product["months"].add(month_key)

        demand_rows = []
        for product_id, values in demand_by_product.items():
            demand_rows.append({
                "id": product_id,
                "product_id": product_id,
                "name": values["name"],
                "sku": values["sku"],
                "warehouse_names": ", ".join(sorted(values["warehouse_names"])),
                "channel_names": ", ".join(
                    "Mayoreo" if item == "wholesale" else "Minorista"
                    for item in sorted(values["channels"])
                ),
                "month_names": ", ".join(sorted(values["months"], reverse=True)),
                "open_demand_qty": values["open"],
                "reserved_qty": values["ready"],
                "incoming_purchase_qty": values["incoming"],
                "missing_to_buy_qty": values["net_missing"],
                "coverage_status": (
                    "incoming" if values["net_missing"] <= 0 else "partial"
                ),
            })
        demand_rows.sort(
            key=lambda row: (row["open_demand_qty"], row["missing_to_buy_qty"]),
            reverse=True,
        )
        demand_top_rows = demand_rows[:10]

        chart_data = self._get_chart_data(
            company,
            period,
            channel=channel,
            warehouse_id=warehouse_id,
            supplier_id=supplier_id,
            supplier_type=supplier_type,
            product_ids=product_ids,
            receipt_period=receipt_period,
        )
        requested_pieces = sum(row["open_demand_qty"] for row in demand_rows)
        pieces_to_buy = sum(row["missing_to_buy_qty"] for row in demand_rows)
        covered_pieces = max(requested_pieces - pieces_to_buy, 0.0)
        chart_data["charts"]["demand_pieces"] = {
            "requested": requested_pieces,
            "covered": covered_pieces,
            "to_buy": pieces_to_buy,
            "covered_percent": (
                covered_pieces / requested_pieces * 100.0
                if requested_pieces else 0.0
            ),
            "to_buy_percent": (
                pieces_to_buy / requested_pieces * 100.0
                if requested_pieces else 0.0
            ),
        }
        chart_data["charts"]["waiting_channels"] = {
            "total": waiting_total_pieces,
            "total_orders": waiting_total_orders,
            "wholesale": waiting_pieces["wholesale"],
            "retail": waiting_pieces["retail"],
            "wholesale_percent": (
                waiting_pieces["wholesale"] / waiting_total_pieces * 100.0
                if waiting_total_pieces else 0.0
            ),
            "wholesale_orders": waiting_counts["wholesale"],
            "retail_orders": waiting_counts["retail"],
            "wholesale_sale_ids": list(waiting_order_ids["wholesale"]),
            "retail_sale_ids": list(waiting_order_ids["retail"]),
        }

        warehouses = self.env["stock.warehouse"].search_read(
            [
                ("company_id", "=", company.id),
                ("systore_supply_management", "!=", "excluded"),
            ],
            ["name"], order="name"
        )
        historical_orders = self._historical_purchase_orders(
            company, warehouse_id=warehouse_id, channel=channel,
            supplier_type=supplier_type,
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
            "charts": chart_data["charts"],
            "demand": demand_top_rows,
            "demand_line_ids": all_demand_lines.ids,
            "demand_periods": [
                {"key": month_key, "label": month_key}
                for month_key in available_demand_months
            ],
            "products": product_options,
            "suppliers": supplier_options,
            "rankings": chart_data["rankings"],
            "warehouses": warehouses,
        }

    @api.model
    def _get_chart_data(
        self, company, period, channel=None, warehouse_id=None,
        supplier_id=None, supplier_type=None, product_ids=None, receipt_period=None,
    ):
        """Build lightweight chart totals for the selected calendar month."""
        product_ids = set(product_ids or [])
        purchase_domain = [
            ("company_id", "=", company.id),
            ("warehouse_id", "!=", False),
            ("warehouse_id.systore_supply_management", "!=", "excluded"),
            ("report_date", ">=", period["month_start"]),
            ("report_date", "<", period["month_end"]),
        ]
        if warehouse_id:
            purchase_domain.append(("warehouse_id", "=", warehouse_id))
        if channel:
            purchase_domain.append(("channel", "=", channel))
        if supplier_type:
            purchase_domain.append(("purchase_origin", "=", supplier_type))
        if product_ids:
            purchase_domain.append(("product_id", "in", list(product_ids)))
        base_purchase_lines = self.env["systore.supply.purchase.line"].search(purchase_domain)
        purchase_lines = base_purchase_lines.filtered(
            lambda line: not supplier_id or line.supplier_id.id == supplier_id
        )
        received_qty = sum(purchase_lines.mapped("net_received_qty"))
        pending_qty = sum(purchase_lines.mapped("pending_qty"))
        pieces_total = received_qty + pending_qty
        received_pct = received_qty / pieces_total * 100.0 if pieces_total else 0.0

        products = defaultdict(lambda: {
            "order_ids": set(), "ordered": 0.0, "received": 0.0,
        })
        suppliers = defaultdict(lambda: {
            "order_ids": set(), "ordered": 0.0, "received": 0.0,
        })
        for line in purchase_lines:
            product = products[line.product_id.id]
            product.update({"name": line.product_id.display_name, "sku": line.sku or ""})
            product["order_ids"].add(line.purchase_order_id.id)
            product["ordered"] += line.ordered_qty
            product["received"] += line.net_received_qty

            supplier = suppliers[line.supplier_id.id]
            supplier["name"] = line.supplier_id.display_name
            supplier["order_ids"].add(line.purchase_order_id.id)
            supplier["ordered"] += line.ordered_qty
            supplier["received"] += line.net_received_qty

        debt_orders = self._historical_purchase_orders(
            company, warehouse_id=warehouse_id, channel=channel,
            supplier_type=supplier_type,
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
                    "received_percent": min(received / ordered * 100.0, 100.0) if ordered else 0.0,
                })
            return result

        product_rows = ranking_rows(products, limit=10)
        supplier_rows = ranking_rows(suppliers, limit=10)

        receipt_period = receipt_period or period
        StockMove = self.env["stock.move"].sudo()
        candidate_receipt_moves = StockMove.search([
            ("company_id", "=", company.id),
            ("state", "=", "done"),
            ("location_id.usage", "=", "supplier"),
            ("location_dest_id.usage", "=", "internal"),
            ("date", ">=", receipt_period["utc_start"]),
            ("date", "<", receipt_period["utc_end"]),
        ])
        received_products = defaultdict(lambda: {
            "gross": 0.0, "returned": 0.0, "line_ids": set(),
            "supplier_usd_gross": 0.0, "supplier_usd_returned": 0.0,
            "supplier_mxn_gross": 0.0, "supplier_mxn_returned": 0.0,
            "net_cost_mxn_gross": 0.0, "net_cost_mxn_returned": 0.0,
            "has_international": False, "has_national": False,
        })
        PurchaseSnapshot = self.env["systore.supply.purchase.line"]

        def move_purchase_data(move):
            purchase_line = (
                move.purchase_line_id
                if "purchase_line_id" in move._fields and move.purchase_line_id
                else move.origin_returned_move_id.purchase_line_id
                if move.origin_returned_move_id
                and "purchase_line_id" in move.origin_returned_move_id._fields
                else self.env["purchase.order.line"]
            )
            order = purchase_line.order_id if purchase_line else self.env["purchase.order"]
            purchase_origins = list(filter(None, [
                move.picking_id.origin,
                move.origin_returned_move_id.picking_id.origin
                if move.origin_returned_move_id else False,
            ]))
            if not order and purchase_origins:
                order = self.env["purchase.order"].sudo().search([
                    ("company_id", "=", company.id),
                    ("name", "in", purchase_origins),
                    ("state", "in", ["purchase", "done"]),
                ], limit=1)
                matching_lines = order.order_line.filtered(
                    lambda line: not line.display_type and line.product_id == move.product_id
                )
                if len(matching_lines) == 1:
                    purchase_line = matching_lines
            partner = order.partner_id if order else move.picking_id.partner_id
            return purchase_line, order, partner

        def move_matches_filters(move, partner, order):
            warehouse = move.picking_type_id.warehouse_id
            if not warehouse or not warehouse._systore_is_managed_for_supply():
                return False
            if warehouse_id and warehouse.id != warehouse_id:
                return False
            internal_location = (
                move.location_dest_id
                if move.location_dest_id.usage == "internal"
                else move.location_id
            )
            resolved_channel = warehouse._systore_resolved_supply_channel(
                internal_location
            )
            if channel and resolved_channel != channel:
                return False
            if supplier_type and (
                not order
                or order._systore_resolved_purchase_origin() != supplier_type
            ):
                return False
            return not supplier_id or (partner and partner.id == supplier_id)

        def move_quantities_and_costs(move, purchase_line, order):
            raw_qty = PurchaseSnapshot._move_done_qty(move)
            display_qty = raw_qty
            if move.product_uom and move.product_id.uom_id and move.product_uom != move.product_id.uom_id:
                display_qty = move.product_uom._compute_quantity(
                    raw_qty, move.product_id.uom_id
                )
            cost_qty = raw_qty
            if purchase_line and move.product_uom and purchase_line.product_uom:
                if move.product_uom != purchase_line.product_uom:
                    cost_qty = move.product_uom._compute_quantity(
                        raw_qty, purchase_line.product_uom
                    )
            international = bool(
                order and order._systore_resolved_purchase_origin() == "international"
            )
            supplier_usd = (
                cost_qty * (purchase_line.x_gross_usd or 0.0)
                if international and purchase_line else 0.0
            )
            supplier_mxn = supplier_usd * (order.x_exchange_rate or 0.0) if order else 0.0
            net_cost_mxn = (
                cost_qty * order._systore_line_cost_mxn(purchase_line)
                if order and purchase_line else 0.0
            )
            return display_qty, supplier_usd, supplier_mxn, net_cost_mxn, international

        period_start = fields.Datetime.to_datetime(receipt_period["utc_start"])
        period_end = fields.Datetime.to_datetime(receipt_period["utc_end"])
        qualifying_orders = self.env["purchase.order"].sudo()
        first_receipt_by_order = {}
        for move in candidate_receipt_moves:
            _purchase_line, order, partner = move_purchase_data(move)
            if not order or not partner or not move_matches_filters(move, partner, order):
                continue
            if order.id not in first_receipt_by_order:
                first_receipt_by_order[order.id] = fields.Datetime.to_datetime(
                    PurchaseSnapshot._first_receipt_date(order)
                )
            first_receipt = first_receipt_by_order[order.id]
            if first_receipt and period_start <= first_receipt < period_end:
                qualifying_orders |= order

        # El rango selecciona la cohorte por primera recepción. Una vez que la
        # OC pertenece a esa cohorte, todas sus recepciones y devoluciones
        # históricas actualizan el resultado sin moverla a otro mes.
        if qualifying_orders:
            receipt_moves = StockMove.search([
                ("company_id", "=", company.id),
                ("state", "=", "done"),
                ("location_id.usage", "=", "supplier"),
                ("location_dest_id.usage", "=", "internal"),
                "|",
                ("purchase_line_id.order_id", "in", qualifying_orders.ids),
                ("picking_id.origin", "in", qualifying_orders.mapped("name")),
            ])
            return_moves = StockMove.search([
                ("company_id", "=", company.id),
                ("state", "=", "done"),
                ("location_id.usage", "=", "internal"),
                ("location_dest_id.usage", "=", "supplier"),
                "|", "|",
                ("purchase_line_id.order_id", "in", qualifying_orders.ids),
                (
                    "origin_returned_move_id.purchase_line_id.order_id",
                    "in",
                    qualifying_orders.ids,
                ),
                (
                    "origin_returned_move_id.picking_id.origin",
                    "in",
                    qualifying_orders.mapped("name"),
                ),
            ])
        else:
            receipt_moves = StockMove.browse()
            return_moves = StockMove.browse()

        for move in receipt_moves:
            purchase_line, order, partner = move_purchase_data(move)
            if (
                not order
                or order not in qualifying_orders
                or not partner
                or (product_ids and move.product_id.id not in product_ids)
                or not move_matches_filters(move, partner, order)
            ):
                continue
            qty, supplier_usd, supplier_mxn, net_cost_mxn, international = (
                move_quantities_and_costs(move, purchase_line, order)
            )
            values = received_products[(partner.id, move.product_id.id)]
            values["partner_name"] = partner.display_name
            values["name"] = move.product_id.display_name
            values["sku"] = move.product_id.default_code or ""
            values["gross"] += qty
            values["supplier_usd_gross"] += supplier_usd
            values["supplier_mxn_gross"] += supplier_mxn
            values["net_cost_mxn_gross"] += net_cost_mxn
            values["has_international"] |= international
            values["has_national"] |= bool(order and not international)
            if purchase_line:
                values["line_ids"].add(purchase_line.id)

        # Una sola recepción real califica la OC. Desde ese momento, "Solicitadas"
        # representa todas sus líneas, incluso las que aún no tienen recepción.
        for order in qualifying_orders:
            international = order._systore_resolved_purchase_origin() == "international"
            for line in order.order_line.filtered(
                lambda item: (
                    not item.display_type
                    and item.product_id
                    and (not product_ids or item.product_id.id in product_ids)
                )
            ):
                values = received_products[(order.partner_id.id, line.product_id.id)]
                values["partner_name"] = order.partner_id.display_name
                values["name"] = line.product_id.display_name
                values["sku"] = line.product_id.default_code or ""
                values["line_ids"].add(line.id)
                values["has_international"] |= international
                values["has_national"] |= not international

        for move in return_moves:
            purchase_line, order, partner = move_purchase_data(move)
            key = (partner.id, move.product_id.id) if partner else False
            if (
                not key or key not in received_products
                or (product_ids and move.product_id.id not in product_ids)
                or not move_matches_filters(move, partner, order)
            ):
                continue
            qty, supplier_usd, supplier_mxn, net_cost_mxn, international = (
                move_quantities_and_costs(move, purchase_line, order)
            )
            values = received_products[key]
            values["returned"] += qty
            values["supplier_usd_returned"] += supplier_usd
            values["supplier_mxn_returned"] += supplier_mxn
            values["net_cost_mxn_returned"] += net_cost_mxn
            values["has_international"] |= international
            values["has_national"] |= bool(order and not international)
            if purchase_line:
                values["line_ids"].add(purchase_line.id)

        received_by_supplier = defaultdict(lambda: {
            "name": "", "ordered": 0.0, "gross": 0.0,
            "returned": 0.0, "net": 0.0, "pending": 0.0,
            "supplier_cost_usd": 0.0, "supplier_cost_mxn": 0.0,
            "net_cost_mxn": 0.0,
            "has_international": False, "has_national": False,
            "status_values": {
                status: {
                    "qty": 0.0, "cost_usd": 0.0,
                    "cost_mxn": 0.0, "cost_net": 0.0,
                }
                for status in ("ordered", "gross", "returned", "net", "pending")
            },
        })
        for (partner_id, product_id), values in received_products.items():
            product = self.env["product.product"].browse(product_id)
            ordered = pending = 0.0
            ordered_cost_usd = ordered_cost_mxn = ordered_cost_net = 0.0
            pending_cost_usd = pending_cost_mxn = pending_cost_net = 0.0
            for line in self.env["purchase.order.line"].browse(values["line_ids"]):
                line_ordered_cost_qty = line.product_qty or 0.0
                _, _, line_net, _ = PurchaseSnapshot._line_receipt_quantities(line)
                line_pending_cost_qty = max(line_ordered_cost_qty - line_net, 0.0)
                line_order = line.order_id
                line_international = (
                    line_order._systore_resolved_purchase_origin() == "international"
                )
                line_supplier_usd = (
                    line.x_gross_usd or 0.0
                ) if line_international else 0.0
                line_supplier_mxn = line_supplier_usd * (
                    line_order.x_exchange_rate or 0.0
                )
                line_net_unit_mxn = line_order._systore_line_cost_mxn(line)
                ordered_cost_usd += line_ordered_cost_qty * line_supplier_usd
                ordered_cost_mxn += line_ordered_cost_qty * line_supplier_mxn
                ordered_cost_net += line_ordered_cost_qty * line_net_unit_mxn
                pending_cost_usd += line_pending_cost_qty * line_supplier_usd
                pending_cost_mxn += line_pending_cost_qty * line_supplier_mxn
                pending_cost_net += line_pending_cost_qty * line_net_unit_mxn
                line_ordered = line_ordered_cost_qty
                if line.product_uom and product.uom_id and line.product_uom != product.uom_id:
                    line_ordered = line.product_uom._compute_quantity(line_ordered, product.uom_id)
                    line_net = line.product_uom._compute_quantity(line_net, product.uom_id)
                ordered += line_ordered
                pending += max(line_ordered - line_net, 0.0)
            gross = values["gross"]
            returned = values["returned"]
            net = max(gross - returned, 0.0)
            supplier_cost_usd = max(
                values["supplier_usd_gross"] - values["supplier_usd_returned"], 0.0
            )
            supplier_cost_mxn = max(
                values["supplier_mxn_gross"] - values["supplier_mxn_returned"], 0.0
            )
            net_cost_mxn = max(
                values["net_cost_mxn_gross"] - values["net_cost_mxn_returned"], 0.0
            )
            status_values = {
                "ordered": {
                    "qty": ordered, "cost_usd": ordered_cost_usd,
                    "cost_mxn": ordered_cost_mxn, "cost_net": ordered_cost_net,
                },
                "gross": {
                    "qty": gross, "cost_usd": values["supplier_usd_gross"],
                    "cost_mxn": values["supplier_mxn_gross"],
                    "cost_net": values["net_cost_mxn_gross"],
                },
                "returned": {
                    "qty": returned, "cost_usd": values["supplier_usd_returned"],
                    "cost_mxn": values["supplier_mxn_returned"],
                    "cost_net": values["net_cost_mxn_returned"],
                },
                "net": {
                    "qty": net, "cost_usd": supplier_cost_usd,
                    "cost_mxn": supplier_cost_mxn, "cost_net": net_cost_mxn,
                },
                "pending": {
                    "qty": pending, "cost_usd": pending_cost_usd,
                    "cost_mxn": pending_cost_mxn, "cost_net": pending_cost_net,
                },
            }
            row = {
                "id": product_id,
                "supplier_id": partner_id,
                "name": values["name"],
                "sku": values["sku"],
                "ordered": ordered,
                "gross": gross,
                "returned": returned,
                "net": net,
                "pending": pending,
                "supplier_cost_usd": supplier_cost_usd,
                "supplier_cost_mxn": supplier_cost_mxn,
                "net_cost_mxn": net_cost_mxn,
                "values": status_values,
            }
            supplier_values = received_by_supplier[partner_id]
            supplier_values["name"] = values["partner_name"]
            for metric in ("ordered", "gross", "returned", "net", "pending"):
                supplier_values[metric] += row[metric]
            for metric in ("supplier_cost_usd", "supplier_cost_mxn", "net_cost_mxn"):
                supplier_values[metric] += row[metric]
            supplier_values["has_international"] |= values["has_international"]
            supplier_values["has_national"] |= values["has_national"]
            for status, status_metrics in status_values.items():
                for metric, amount in status_metrics.items():
                    supplier_values["status_values"][status][metric] += amount

        received_supplier_rows = []
        for partner_id, values in received_by_supplier.items():
            received_supplier_rows.append({
                "id": partner_id,
                "name": values["name"],
                "ordered": values["ordered"],
                "gross": values["gross"],
                "returned": values["returned"],
                "net": values["net"],
                "pending": values["pending"],
                "supplier_cost_usd": values["supplier_cost_usd"],
                "supplier_cost_mxn": values["supplier_cost_mxn"],
                "net_cost_mxn": values["net_cost_mxn"],
                "is_international": values["has_international"],
                "origin": (
                    "mixed" if values["has_international"] and values["has_national"]
                    else "international" if values["has_international"]
                    else "national"
                ),
                "values": values["status_values"],
            })
        received_supplier_rows.sort(key=lambda row: row["gross"], reverse=True)
        received_totals = {
            "ordered": 0.0, "gross": 0.0, "returned": 0.0,
            "net": 0.0, "pending": 0.0, "is_international": False,
            "values": {
                status: {
                    "qty": 0.0, "cost_usd": 0.0,
                    "cost_mxn": 0.0, "cost_net": 0.0,
                }
                for status in ("ordered", "gross", "returned", "net", "pending")
            },
        }
        for supplier_row in received_supplier_rows:
            received_totals["is_international"] |= supplier_row["is_international"]
            for status in ("ordered", "gross", "returned", "net", "pending"):
                received_totals[status] += supplier_row[status]
                for metric, amount in supplier_row["values"][status].items():
                    received_totals["values"][status][metric] += amount

        supplier_palette = [
            "#1f6f8b", "#f4b942", "#2e8b57", "#7b61a8", "#d46b45", "#5d8797",
        ]

        def purchased_supplier_chart(cost_mode):
            supplier_values = sorted(
                (
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "value": row["values"]["ordered"][cost_mode],
                    }
                    for row in received_supplier_rows
                    if row["values"]["ordered"][cost_mode] > 0
                ),
                key=lambda row: row["value"],
                reverse=True,
            )
            total = sum(row["value"] for row in supplier_values)
            segments = supplier_values[:5]
            other_value = sum(row["value"] for row in supplier_values[5:])
            if other_value:
                segments.append({
                    "id": False,
                    "name": "Otros proveedores",
                    "value": other_value,
                })
            gradient_parts = []
            gradient_cursor = 0.0
            for index, segment in enumerate(segments):
                segment["color"] = supplier_palette[index % len(supplier_palette)]
                segment["percent"] = (
                    segment["value"] / total * 100.0 if total else 0.0
                )
                gradient_end = gradient_cursor + segment["percent"]
                gradient_parts.append(
                    f'{segment["color"]} {gradient_cursor:.4f}% {gradient_end:.4f}%'
                )
                gradient_cursor = gradient_end
            return {
                "total": total,
                "segments": segments,
                "style": (
                    "background: conic-gradient(" + ", ".join(gradient_parts) + ");"
                    if gradient_parts else ""
                ),
            }

        purchased_by_supplier = {
            cost_mode: purchased_supplier_chart(cost_mode)
            for cost_mode in ("cost_usd", "cost_mxn", "cost_net")
        }

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
            max_debt_mxn = max((row["debt"] for row in rows), default=0.0)
            max_debt_usd = max((row["debt_usd"] for row in rows), default=0.0)
            for row in rows:
                row["debt_percent"] = (
                    row["debt"] / max_debt_mxn * 100.0 if max_debt_mxn else 0.0
                )
                row["debt_percent_mxn"] = row["debt_percent"]
                row["debt_percent_usd"] = (
                    row["debt_usd"] / max_debt_usd * 100.0 if max_debt_usd else 0.0
                )
            return rows[:10]

        national_debts = debt_rows("national")
        international_debts = debt_rows("international")
        credit_rows = self._supplier_credit_rows(
            company,
            supplier_id=supplier_id,
            supplier_type=supplier_type,
        )

        return {
            "charts": {
                "pieces": {
                    "total": pieces_total,
                    "received": received_qty,
                    "pending": pending_qty,
                    "received_percent": received_pct,
                },
                "purchased_by_supplier": purchased_by_supplier,
            },
            "rankings": {
                "products": product_rows,
                "received_products_by_supplier": received_supplier_rows,
                "received_products_totals": received_totals,
                "suppliers": supplier_rows,
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
                "credit_suppliers": credit_rows,
                "credit_provider_count": len(credit_rows),
            },
        }
