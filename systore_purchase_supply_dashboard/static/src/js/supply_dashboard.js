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
        const today = new Date();
        const first = new Date(today.getFullYear(), today.getMonth(), 1);
        const last = new Date(today.getFullYear(), today.getMonth() + 1, 0);
        this.state = useState({
            loading: true,
            refreshing: false,
            data: { kpis: {}, purchases: [], demand: [], trace: [], suppliers: [], warehouses: [], counts: {} },
            filters: {
                date_from: this.toISODate(first),
                date_to: this.toISODate(last),
                channel: "",
                warehouse_id: "",
            },
        });
        onWillStart(() => this.loadData());
    }

    toISODate(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
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
            const result = await this.orm.call("systore.supply.dashboard", "action_refresh", []);
            await this.loadData();
            this.notification.add(
                `Actualización terminada: ${result.purchases} líneas de compra, ${result.demand} de demanda y ${result.trace} de trazabilidad.`,
                { type: "success" }
            );
        } finally {
            this.state.refreshing = false;
        }
    }

    onDateFrom(event) {
        this.state.filters.date_from = event.target.value;
    }

    onDateTo(event) {
        this.state.filters.date_to = event.target.value;
    }

    onChannel(event) {
        this.state.filters.channel = event.target.value;
    }

    onWarehouse(event) {
        this.state.filters.warehouse_id = event.target.value;
    }

    clearDates() {
        this.state.filters.date_from = "";
        this.state.filters.date_to = "";
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
        return { wholesale: "Mayoreo", marketplace: "Marketplace", other: "Otro" }[value] || "Otro";
    }

    paymentLabel(value) {
        return { pending: "Pendiente", partial: "Parcial", paid: "Pagada" }[value] || "Pendiente";
    }

    coverageLabel(value) {
        return {
            stock: "Con existencia",
            incoming: "Con compras",
            shortage: "Falta comprar",
            no_demand: "Sin demanda",
        }[value] || value;
    }

    badgeClass(value) {
        if (["paid", "stock", "no_demand"].includes(value)) {
            return "text-bg-success";
        }
        if (["partial", "incoming"].includes(value)) {
            return "text-bg-warning";
        }
        return "text-bg-danger";
    }

    openAction(xmlId) {
        return this.action.doAction(xmlId);
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

