/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";


export class SystoreSupplyDashboard extends Component {
    static template = "systore_purchase_supply_dashboard.SupplyDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.openIds = this.openIds.bind(this);
        this.openAction = this.openAction.bind(this);
        this.openPurchaseLines = this.openPurchaseLines.bind(this);
        this.openRecord = this.openRecord.bind(this);
        const today = new Date();
        const currentMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
        const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate();
        this.state = useState({
            loading: true,
            refreshing: false,
            data: {
                kpis: {},
                charts: {
                    readiness: [],
                    readiness_total: 0,
                    readiness_pieces: 0,
                    channels: { total: 0, wholesale: 0, retail: 0, wholesale_percent: 0 },
                    pieces: { total: 0, received: 0, pending: 0, received_percent: 0 },
                },
                rankings: {
                    products: [], received_products: [], received_products_by_supplier: [], suppliers: [], debts: [],
                    debts_national: [], debts_international: [],
                    debt_national_mxn: 0,
                    debt_international_mxn: 0,
                    debt_international_usd: 0,
                },
                purchases: [], demand: [], trace: [], suppliers: [], warehouses: [], counts: {},
            },
            filters: {
                period_month: currentMonth,
                date_from: `${currentMonth}-01`,
                date_to: `${currentMonth}-${String(lastDay).padStart(2, "0")}`,
                received_cost_mode: "cost_net",
                channel: "",
                warehouse_id: "",
                supplier_id: "",
            },
        });
        onWillStart(() => this.loadData());
    }

    async loadData() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(
                "systore.supply.dashboard",
                "get_dashboard_data",
                [],
                { filters: { ...this.state.filters } }
            );
        } finally {
            this.state.loading = false;
        }
    }

    async refreshData() {
        this.state.refreshing = true;
        try {
            const result = await this.orm.call(
                "systore.supply.dashboard",
                "action_refresh",
                [],
                { period_month: this.state.filters.period_month }
            );
            await this.loadData();
            this.notification.add(
                `Actualización terminada para ${result.period_month}: ${result.demand} líneas de demanda.`,
                { type: "success" }
            );
        } finally {
            this.state.refreshing = false;
        }
    }

    onPeriodMonth(event) {
        this.state.filters.period_month = event.target.value;
        const [year, month] = event.target.value.split("-").map(Number);
        const lastDay = new Date(year, month, 0).getDate();
        this.state.filters.date_from = `${event.target.value}-01`;
        this.state.filters.date_to = `${event.target.value}-${String(lastDay).padStart(2, "0")}`;
        this.state.filters.supplier_id = "";
    }

    onChannel(event) {
        this.state.filters.channel = event.target.value;
        this.state.filters.supplier_id = "";
    }

    onDateFrom(event) {
        this.state.filters.date_from = event.target.value;
    }

    onDateTo(event) {
        this.state.filters.date_to = event.target.value;
    }

    onReceivedCostMode(event) {
        this.state.filters.received_cost_mode = event.target.value;
    }

    onWarehouse(event) {
        this.state.filters.warehouse_id = event.target.value;
        this.state.filters.supplier_id = "";
    }

    onSupplier(event) {
        this.state.filters.supplier_id = event.target.value;
    }

    currentMonth() {
        const today = new Date();
        const month = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
        const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate();
        this.state.filters.period_month = month;
        this.state.filters.date_from = `${month}-01`;
        this.state.filters.date_to = `${month}-${String(lastDay).padStart(2, "0")}`;
        this.state.filters.supplier_id = "";
        this.loadData();
    }

    relationName(value) {
        return Array.isArray(value) ? value[1] : "";
    }

    formatQty(value) {
        return new Intl.NumberFormat("es-MX", { maximumFractionDigits: 2 }).format(value || 0);
    }

    formatMoney(value) {
        return new Intl.NumberFormat("es-MX", {
            style: "currency",
            currency: "MXN",
            maximumFractionDigits: 2,
        }).format(value || 0);
    }

    formatUsd(value) {
        return new Intl.NumberFormat("es-MX", {
            style: "currency",
            currency: "USD",
            maximumFractionDigits: 2,
        }).format(value || 0);
    }

    formatReceivedValue(supplier, status) {
        const mode = this.state.filters.received_cost_mode;
        if (mode !== "cost_net" && !supplier.is_international) {
            return "—";
        }
        const value = supplier.values?.[status]?.[mode] || 0;
        return mode === "cost_usd" ? this.formatUsd(value) : this.formatMoney(value);
    }

    formatPercent(value) {
        return `${this.formatQty(value)}%`;
    }

    formatDate(value) {
        if (!value) {
            return "Sin recepción";
        }
        return value.slice(0, 10);
    }

    channelLabel(value) {
        return { wholesale: "Mayoreo", retail: "Minorista" }[value] || "Minorista";
    }

    paymentLabel(value) {
        return { pending: "Pendiente", partial: "Parcial", paid: "Pagada" }[value] || "Pendiente";
    }

    coverageLabel(value) {
        return { partial: "Parcial" }[value] || value;
    }

    badgeClass(value) {
        if (["paid", "stock", "no_demand"].includes(value)) {
            return "text-bg-success";
        }
        if (["incoming"].includes(value)) {
            return "text-bg-warning";
        }
        return "text-bg-danger";
    }

    openAction(xmlId) {
        return this.action.doAction(xmlId);
    }

    openIds(model, name, ids) {
        if (!ids?.length) {
            return;
        }
        return this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: model,
            views: [[false, "list"], [false, "form"]],
            domain: [["id", "in", ids]],
            target: "current",
        });
    }

    purchaseDomain(extra = []) {
        const month = this.state.filters.period_month;
        const [year, monthNumber] = month.split("-").map(Number);
        const nextMonth = new Date(Date.UTC(year, monthNumber, 1));
        const nextMonthKey = `${nextMonth.getUTCFullYear()}-${String(nextMonth.getUTCMonth() + 1).padStart(2, "0")}-01`;
        const domain = [
            ["report_date", ">=", `${month}-01`],
            ["report_date", "<", nextMonthKey],
        ];
        if (this.state.filters.channel) {
            domain.push(["channel", "=", this.state.filters.channel]);
        }
        if (this.state.filters.warehouse_id) {
            domain.push(["warehouse_id", "=", Number(this.state.filters.warehouse_id)]);
        }
        if (this.state.filters.supplier_id) {
            domain.push(["supplier_id", "=", Number(this.state.filters.supplier_id)]);
        }
        return [...domain, ...extra];
    }

    openPurchaseLines(name, extra = []) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: "systore.supply.purchase.line",
            views: [[false, "list"], [false, "pivot"], [false, "graph"]],
            domain: this.purchaseDomain(extra),
            target: "current",
        });
    }

    openRecord(model, relation) {
        if (!Array.isArray(relation)) {
            return;
        }
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: relation[0],
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("systore_supply_dashboard", SystoreSupplyDashboard);
