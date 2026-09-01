/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class SystoreSalesCostDashboard extends Component {
    static template = "systore_sales_cost_analytics.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            data: {
                currency: "MXN",
                filters: {sales_channels: [], accounts: [], partners: [], products: [], vendors: []},
                kpis: {}, trend: [], trend_max: 0, channels: [], products: [], vendors: [], pie_channels: [], pie_customers: [], pie_products: [], pie_vendors: [], return_channels: [], reconciliation: [],
            },
            filters: {
                date_from: "",
                date_to: "",
                sale_state: "",
                sales_channel: "",
                account_id: "",
                partner_id: "",
                product_id: "",
                vendor_id: "",
            },
        });
        onWillStart(() => this.loadData());
    }

    async loadData() {
        this.state.loading = true;
        const payload = { ...this.state.filters };
        for (const key of ["account_id", "partner_id", "product_id", "vendor_id"]) {
            if (payload[key]) {
                payload[key] = Number(payload[key]);
            }
        }
        const data = await this.orm.call("systore.sales.cost.line", "get_dashboard_data", [payload]);
        this.state.data = data;
        this.state.filters.date_from = data.applied_filters.date_from;
        this.state.filters.date_to = data.applied_filters.date_to;
        this.state.loading = false;
    }

    onFilterChange(ev) {
        const field = ev.target.dataset.field;
        this.state.filters[field] = ev.target.value;
        this.loadData();
    }

    applyDates() {
        this.loadData();
    }

    clearFilters() {
        Object.assign(this.state.filters, {
            sale_state: "",
            sales_channel: "",
            account_id: "",
            partner_id: "",
            product_id: "",
            vendor_id: "",
        });
        this.loadData();
    }

    setPeriod(period) {
        const now = new Date();
        const y = now.getFullYear();
        const m = now.getMonth();
        let from;
        let to;
        if (period === "month") {
            from = new Date(y, m, 1);
            to = new Date(y, m + 1, 0);
        } else if (period === "previous_month") {
            from = new Date(y, m - 1, 1);
            to = new Date(y, m, 0);
        } else if (period === "year") {
            from = new Date(y, 0, 1);
            to = new Date(y, 11, 31);
        }
        const iso = (d) => {
            const yy = d.getFullYear();
            const mm = String(d.getMonth() + 1).padStart(2, "0");
            const dd = String(d.getDate()).padStart(2, "0");
            return `${yy}-${mm}-${dd}`;
        };
        this.state.filters.date_from = iso(from);
        this.state.filters.date_to = iso(to);
        this.loadData();
    }

    money(value) {
        const currency = this.state.data?.currency || "MXN";
        return new Intl.NumberFormat("es-MX", {
            style: "currency",
            currency,
            maximumFractionDigits: 2,
        }).format(value || 0);
    }

    number(value) {
        return new Intl.NumberFormat("es-MX", { maximumFractionDigits: 2 }).format(value || 0);
    }

    percent(value) {
        return new Intl.NumberFormat("es-MX", {
            style: "percent",
            minimumFractionDigits: 1,
            maximumFractionDigits: 1,
        }).format(value || 0);
    }

    barWidth(value, maxValue) {
        if (!maxValue) return "0%";
        return `${Math.max(2, Math.min(100, (Math.abs(value) / maxValue) * 100))}%`;
    }

    currentDomain(extraDomain = []) {
        const f = this.state.filters;
        const domain = [];
        if (f.date_from) domain.push(["invoice_date", ">=", f.date_from]);
        if (f.date_to) domain.push(["invoice_date", "<=", f.date_to]);
        if (f.sale_state) domain.push(["sale_state", "=", f.sale_state]);
        if (f.sales_channel) domain.push(["sales_channel", "=", f.sales_channel]);
        if (f.account_id) domain.push(["account_id", "=", Number(f.account_id)]);
        if (f.partner_id) domain.push(["partner_id", "=", Number(f.partner_id)]);
        if (f.product_id) domain.push(["product_id", "=", Number(f.product_id)]);
        if (f.vendor_id) domain.push(["vendor_id", "=", Number(f.vendor_id)]);
        return domain.concat(extraDomain || []);
    }


    pieStyle(rows) {
        if (!rows || !rows.length) {
            return "background:#f2f4f7";
        }
        const palette = ["#6172f3", "#12b76a", "#f79009", "#ee46bc", "#06aed4", "#f04438", "#7a5af8", "#98a2b3"];
        let cursor = 0;
        const parts = rows.map((row, index) => {
            const start = cursor;
            cursor += (row.share || 0) * 100;
            return `${palette[index % palette.length]} ${start}% ${cursor}%`;
        });
        return `background:conic-gradient(${parts.join(",")})`;
    }

    pieLegendStyle(index) {
        const palette = ["#6172f3", "#12b76a", "#f79009", "#ee46bc", "#06aed4", "#f04438", "#7a5af8", "#98a2b3"];
        return `background:${palette[index % palette.length]}`;
    }

    openPieRow(row) {
        if (row && row.domain && row.domain.length) {
            this.openReport(row.domain);
        }
    }

    openReport(extraDomain = []) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Reporte consolidado",
            res_model: "systore.sales.cost.line",
            view_mode: "list,pivot,graph,form",
            views: [[false, "list"], [false, "pivot"], [false, "graph"], [false, "form"]],
            domain: this.currentDomain(extraDomain),
            target: "current",
        });
    }

    openRow(row) {
        this.openReport(row.domain || []);
    }
}

registry.category("actions").add("systore_sales_cost_dashboard", SystoreSalesCostDashboard);
