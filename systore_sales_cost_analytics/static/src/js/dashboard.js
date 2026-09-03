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
            openFilter: "",
            pieMetrics: { channels: "sales", customers: "sales", contacts: "sales", products: "sales", vendors: "sales", categories: "sales", conditions: "sales" },
            data: {
                currency: "MXN",
                filters: {sales_channels: [], accounts: [], partners: [], contacts: [], products: [], vendors: [], salespersons: []},
                kpis: {}, trend: [], channels: [], products: [], vendors: [], return_channels: [], reconciliation: [],
            },
            filters: {
                date_from: "",
                date_to: "",
                sale_state: [],
                sales_channel: [],
                account_id: [],
                partner_id: [],
                customer_contact_id: [],
                product_id: [],
                vendor_id: [],
                salesperson_id: [],
            },
        });
        onWillStart(() => this.loadData());
    }

    async loadData() {
        this.state.loading = true;
        const payload = { ...this.state.filters };
        for (const key of ["account_id", "partner_id", "customer_contact_id", "product_id", "vendor_id", "salesperson_id"]) {
            payload[key] = (payload[key] || []).map((value) => Number(value));
        }
        const data = await this.orm.call("systore.sales.cost.line", "get_dashboard_data", [payload]);
        this.state.data = data;
        this.state.filters.date_from = data.applied_filters.date_from;
        this.state.filters.date_to = data.applied_filters.date_to;
        this.state.loading = false;
    }

    statusOptions() {
        return [
            { id: "sale", name: "Venta" },
            { id: "return", name: "Devolución en tránsito" },
        ];
    }

    filterKey(value) {
        return value === null || value === undefined ? "" : `${value}`;
    }

    isFilterSelected(field, value) {
        const key = this.filterKey(value);
        return (this.state.filters[field] || []).some((item) => this.filterKey(item) === key);
    }

    toggleFilterMenu(field) {
        this.state.openFilter = this.state.openFilter === field ? "" : field;
    }

    toggleFilterValue(field, value) {
        const values = [...(this.state.filters[field] || [])];
        const key = this.filterKey(value);
        const index = values.findIndex((item) => this.filterKey(item) === key);
        if (index >= 0) {
            values.splice(index, 1);
        } else {
            values.push(value);
        }
        this.state.filters[field] = values;
        if (field === "sale_state") {
            this.syncPieMetricsToSaleState();
        }
        this.loadData();
    }

    clearOneFilter(field) {
        this.state.filters[field] = [];
        this.loadData();
    }

    selectedLabels(field, options) {
        const selected = this.state.filters[field] || [];
        if (!selected.length) return [];
        const normalizedOptions = (options || []).map((option) => {
            if (typeof option === "string") {
                return { id: option, name: option };
            }
            return option;
        });
        const labels = selected.map((value) => {
            const key = this.filterKey(value);
            const option = normalizedOptions.find((item) => this.filterKey(item.id) === key);
            return option ? option.name : key;
        });
        if (labels.length <= 2) return labels;
        return [labels[0], labels[1], `+${labels.length - 2}`];
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
        this.state.openFilter = "";
        Object.assign(this.state.filters, {
            sale_state: [],
            sales_channel: [],
            account_id: [],
            partner_id: [],
            customer_contact_id: [],
            product_id: [],
            vendor_id: [],
            salesperson_id: [],
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


    chartX(index) {
        const rows = this.state.data?.trend || [];
        if (rows.length <= 1) return 520;
        return 60 + (index * 920) / (rows.length - 1);
    }

    chartBounds() {
        const rows = this.state.data?.trend || [];
        const values = rows.flatMap((row) => [row.net_sales || 0, row.net_cost || 0, row.profit || 0]);
        let min = Math.min(0, ...values);
        let max = Math.max(0, ...values);
        if (min === max) {
            max = min + 1;
        }
        const pad = (max - min) * 0.08;
        return { min: min - pad, max: max + pad };
    }

    chartY(value) {
        const { min, max } = this.chartBounds();
        const ratio = ((value || 0) - min) / (max - min);
        return 270 - ratio * 250;
    }

    linePoints(field) {
        return (this.state.data?.trend || [])
            .map((row, index) => `${this.chartX(index)},${this.chartY(row[field] || 0)}`)
            .join(" ");
    }

    showXAxisLabel(index) {
        const length = (this.state.data?.trend || []).length;
        if (length <= 12) return true;
        const step = Math.ceil(length / 10);
        return index % step === 0 || index === length - 1;
    }

    compositionShare(value) {
        const gross = Math.max(0, this.state.data?.kpis?.gross_sales || 0);
        if (!gross) return 0;
        return Math.max(0, Math.min(1, (value || 0) / gross));
    }

    compositionWidth(value) {
        return `${this.compositionShare(value) * 100}%`;
    }


    currentDomain(extraDomain = []) {
        const f = this.state.filters;
        const domain = [];
        if (f.date_from) domain.push(["invoice_date", ">=", f.date_from]);
        if (f.date_to) domain.push(["invoice_date", "<=", f.date_to]);
        if (f.sale_state?.length) domain.push(["sale_state", "in", f.sale_state]);
        if (f.sales_channel?.length) domain.push(["sales_channel", "in", f.sales_channel]);
        for (const field of ["account_id", "partner_id", "customer_contact_id", "product_id", "vendor_id", "salesperson_id"]) {
            if (f[field]?.length) domain.push([field, "in", f[field].map(Number)]);
        }
        return domain.concat(extraDomain || []);
    }


    syncPieMetricsToSaleState() {
        const states = this.state.filters.sale_state || [];
        if (states.length !== 1) return;
        const metric = states[0] === "return" ? "returns" : "sales";
        for (const key of ["channels", "customers", "contacts", "products", "vendors", "categories", "conditions"]) {
            this.state.pieMetrics[key] = metric;
        }
    }

    setPieMetric(dimension, metric) {
        this.state.pieMetrics[dimension] = metric;
    }

    pieRows(dimension) {
        const sets = this.state.data?.pie_sets?.[dimension] || {};
        const metric = this.state.pieMetrics[dimension] || "sales";
        return sets[metric] || [];
    }

    pieMetricTitle(metric) {
        if (metric === "returns") return "Devolución en tránsito";
        if (metric === "pieces") return "Piezas";
        return "Venta";
    }

    pieValue(row, dimension) {
        const metric = this.state.pieMetrics[dimension] || "sales";
        if (metric === "pieces") {
            return `${this.number(row.value)} pzas`;
        }
        return `${this.money(row.value)} · ${this.number(row.pieces || 0)} pzas`;
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
