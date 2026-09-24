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
        this.openPurchaseLines = this.openPurchaseLines.bind(this);
        this.openDemandLines = this.openDemandLines.bind(this);
        this.debtRows = this.debtRows.bind(this);
        this.toggleDebtProviders = this.toggleDebtProviders.bind(this);
        this.openDebtReport = this.openDebtReport.bind(this);
        this.debtCutoffLabel = this.debtCutoffLabel.bind(this);
        const today = new Date();
        const currentMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
        const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate();
        this.state = useState({
            loading: true,
            refreshing: false,
            showDemandTable: true,
            showReceivedProductsTable: true,
            showAllInternationalDebt: false,
            showAllNationalDebt: false,
            data: {
                charts: {
                    demand_pieces: { requested: 0, covered: 0, to_buy: 0, covered_percent: 0, to_buy_percent: 0 },
                    waiting_channels: {
                        total: 0, total_orders: 0, wholesale: 0, retail: 0,
                        wholesale_orders: 0, retail_orders: 0, wholesale_percent: 0,
                    },
                    pieces: { total: 0, received: 0, pending: 0, received_percent: 0 },
                    purchased_by_supplier: {
                        cost_usd: { total: 0, segments: [], style: "" },
                        cost_mxn: { total: 0, segments: [], style: "" },
                        cost_net: { total: 0, segments: [], style: "" },
                    },
                },
                rankings: {
                    products: [], received_products_by_supplier: [], suppliers: [],
                    received_products_totals: { values: {} },
                    debts_national: [], debts_international: [],
                    debt_national_mxn: 0,
                    debt_international_mxn: 0,
                    debt_international_usd: 0,
                    debt_cutoff_date: "",
                    credit_suppliers: [],
                    credit_provider_count: 0,
                },
                demand: [], demand_line_ids: [], demand_periods: [], products: [], suppliers: [], warehouses: [],
            },
            openFilter: "",
            productSearch: "",
            filters: {
                period_month: currentMonth,
                demand_period: currentMonth,
                date_from: `${currentMonth}-01`,
                date_to: `${currentMonth}-${String(lastDay).padStart(2, "0")}`,
                received_cost_mode: "cost_usd",
                purchased_cost_mode: "cost_usd",
                foreign_debt_currency: "usd",
                supplier_type: "",
                channel: "",
                warehouse_id: "",
                supplier_id: "",
                product_ids: [],
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
                {
                    filters: {
                        ...this.state.filters,
                        product_ids: [...this.state.filters.product_ids],
                    },
                }
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
                `Actualización terminada para ${result.period_month}: ${result.demand} líneas de demanda, ${result.purchases} de recepción y ${result.trace} de trazabilidad.`,
                { type: "success" }
            );
        } finally {
            this.state.refreshing = false;
        }
    }

    onPeriodMonth(event) {
        this.state.filters.period_month = event.target.value;
        this.state.filters.demand_period = event.target.value;
        const [year, month] = event.target.value.split("-").map(Number);
        const lastDay = new Date(year, month, 0).getDate();
        this.state.filters.date_from = `${event.target.value}-01`;
        this.state.filters.date_to = `${event.target.value}-${String(lastDay).padStart(2, "0")}`;
        this.state.filters.supplier_id = "";
    }

    onDemandPeriod(event) {
        this.state.filters.demand_period = event.target.value;
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

    onPurchasedCostMode(event) {
        this.state.filters.purchased_cost_mode = event.target.value;
    }

    onForeignDebtCurrency(event) {
        this.state.filters.foreign_debt_currency = event.target.value;
    }

    toggleDemandTable() {
        this.state.showDemandTable = !this.state.showDemandTable;
    }

    toggleReceivedProductsTable() {
        this.state.showReceivedProductsTable = !this.state.showReceivedProductsTable;
    }

    debtRows(sector) {
        const rows = sector === "international"
            ? this.state.data.rankings.debts_international
            : this.state.data.rankings.debts_national;
        const expanded = sector === "international"
            ? this.state.showAllInternationalDebt
            : this.state.showAllNationalDebt;
        return expanded ? rows : rows.slice(0, 10);
    }

    toggleDebtProviders(sector) {
        if (sector === "international") {
            this.state.showAllInternationalDebt = !this.state.showAllInternationalDebt;
        } else {
            this.state.showAllNationalDebt = !this.state.showAllNationalDebt;
        }
    }

    async openDebtReport(sector, supplierId = false) {
        const action = await this.orm.call(
            "systore.supply.dashboard",
            "action_open_debt_report",
            [],
            {
                sector,
                filters: {
                    ...this.state.filters,
                    product_ids: [...this.state.filters.product_ids],
                },
                supplier_id: supplierId || false,
            }
        );
        return this.action.doAction(action);
    }

    debtCutoffLabel() {
        const value = this.state.data.rankings.debt_cutoff_date;
        if (!value) {
            return "cierre seleccionado";
        }
        const [year, month, day] = value.split("-").map(Number);
        return new Intl.DateTimeFormat("es-MX", {
            day: "2-digit",
            month: "short",
            year: "numeric",
        }).format(new Date(year, month - 1, day));
    }

    onWarehouse(event) {
        this.state.filters.warehouse_id = event.target.value;
        this.state.filters.supplier_id = "";
    }

    onSupplier(event) {
        this.state.filters.supplier_id = event.target.value;
    }

    onSupplierType(event) {
        this.state.filters.supplier_type = event.target.value;
        this.state.filters.supplier_id = "";
    }

    onProductSearch(event) {
        this.state.productSearch = event.target.value;
    }

    toggleProductFilter() {
        this.state.openFilter = this.state.openFilter === "product_ids" ? "" : "product_ids";
    }

    onProductToggle(event) {
        const productId = Number(event.target.value);
        const selected = new Set(this.state.filters.product_ids);
        if (event.target.checked) {
            selected.add(productId);
        } else {
            selected.delete(productId);
        }
        this.state.filters.product_ids = [...selected];
    }

    clearProductFilter() {
        this.state.filters.product_ids = [];
        this.state.productSearch = "";
    }

    isProductSelected(productId) {
        return this.state.filters.product_ids.includes(productId);
    }

    selectedProductLabels() {
        const selected = new Set(this.state.filters.product_ids);
        const labels = this.state.data.products
            .filter((product) => selected.has(product.id))
            .map((product) => this.productOptionLabel(product));
        if (labels.length <= 2) {
            return labels;
        }
        return [labels[0], labels[1], `+${labels.length - 2}`];
    }

    productOptionLabel(product) {
        return product.sku ? `[${product.sku}] ${product.name || ""}` : (product.name || "Sin nombre");
    }

    filteredProducts() {
        const query = this.state.productSearch.trim().toLocaleLowerCase("es-MX");
        return this.state.data.products.filter((product) => {
            if (!query) {
                return true;
            }
            return `${product.sku || ""} ${product.name || ""}`
                .toLocaleLowerCase("es-MX")
                .includes(query);
        }).slice(0, 100);
    }

    currentMonth() {
        const today = new Date();
        this.selectCalendarMonth(today);
    }

    previousMonth() {
        const today = new Date();
        this.selectCalendarMonth(new Date(today.getFullYear(), today.getMonth() - 1, 1));
    }

    selectCalendarMonth(date) {
        const month = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
        const lastDay = new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
        this.state.filters.period_month = month;
        this.state.filters.demand_period = month;
        this.state.filters.date_from = `${month}-01`;
        this.state.filters.date_to = `${month}-${String(lastDay).padStart(2, "0")}`;
        this.state.filters.supplier_id = "";
        this.loadData();
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

    formatCredit(value, currency) {
        try {
            return new Intl.NumberFormat("es-MX", {
                style: "currency",
                currency: currency || "USD",
                maximumFractionDigits: 2,
            }).format(value || 0);
        } catch {
            return `${this.formatQty(value)} ${currency || ""}`.trim();
        }
    }

    formatForeignDebt(usdValue, mxnValue) {
        return this.state.filters.foreign_debt_currency === "usd"
            ? this.formatUsd(usdValue)
            : this.formatMoney(mxnValue);
    }

    foreignDebtPercent(row) {
        return this.state.filters.foreign_debt_currency === "usd"
            ? row.debt_percent_usd
            : row.debt_percent_mxn;
    }

    formatReceivedValue(supplier, status) {
        const mode = this.state.filters.received_cost_mode;
        if (mode !== "cost_net" && !supplier.is_international) {
            return "—";
        }
        const value = supplier.values?.[status]?.[mode] || 0;
        return mode === "cost_usd" ? this.formatUsd(value) : this.formatMoney(value);
    }

    purchasedSupplierChart() {
        const mode = this.state.filters.purchased_cost_mode;
        return this.state.data.charts.purchased_by_supplier?.[mode]
            || { total: 0, segments: [], style: "" };
    }

    formatPurchasedValue(value) {
        return this.state.filters.purchased_cost_mode === "cost_usd"
            ? this.formatUsd(value)
            : this.formatMoney(value);
    }

    formatPercent(value) {
        return `${this.formatQty(value)}%`;
    }

    coverageLabel(value) {
        return {
            incoming: "Cubierta por compra",
            partial: "Por comprar",
        }[value] || value;
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
            ["warehouse_id", "!=", false],
            ["warehouse_id.systore_supply_management", "!=", "excluded"],
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
        if (this.state.filters.supplier_type) {
            domain.push(["purchase_origin", "=", this.state.filters.supplier_type]);
        }
        if (this.state.filters.product_ids.length) {
            domain.push(["product_id", "in", [...this.state.filters.product_ids]]);
        }
        return [...domain, ...extra];
    }

    openPurchaseLines(name, extra = [], context = {}) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: "systore.supply.purchase.line",
            views: [[false, "list"], [false, "pivot"], [false, "graph"]],
            domain: this.purchaseDomain(extra),
            context,
            target: "current",
        });
    }

    openDemandLines(name, productId = false) {
        const domain = [
            ["warehouse_id", "!=", false],
            ["warehouse_id.systore_supply_management", "!=", "excluded"],
        ];
        domain.push(
            this.state.data.demand_line_ids.length
                ? ["id", "in", this.state.data.demand_line_ids]
                : ["id", "=", 0]
        );
        if (productId) {
            domain.push(["product_id", "=", productId]);
        }
        return this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: "systore.supply.demand.line",
            views: [[false, "list"], [false, "pivot"], [false, "graph"]],
            domain,
            target: "current",
        });
    }

}

registry.category("actions").add("systore_supply_dashboard", SystoreSupplyDashboard);
