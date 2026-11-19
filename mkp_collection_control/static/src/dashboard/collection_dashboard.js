/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class MkpCollectionDashboard extends Component {
    static template = "mkp_collection_control.CollectionDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            filters: this.emptyFilters(),
            data: {
                totals: {},
                counts: {},
                composition: [],
                payment_breakdown: [],
                upcoming: {
                    total: 0,
                    line_count: 0,
                    order_count: 0,
                    order_ids: [],
                    next_date: false,
                },
                options: { months: [], clients: [], states: [], collection_types: [] },
                currency: "MXN",
            },
        });
        onWillStart(() => this.loadData());
    }

    emptyFilters() {
        return {
            date_from: "",
            date_to: "",
            month: "",
            state: "",
            collection_type: "",
            partner_id: "",
            has_killer: false,
            has_coupon: false,
            has_return: false,
        };
    }

    async loadData() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(
                "mkp.collection.line.history",
                "get_dashboard_data",
                [{ ...this.state.filters }]
            );
        } catch (error) {
            this.notification.add(
                error.message || "No fue posible cargar el dashboard de cobranza.",
                { type: "danger" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    async applyFilters() {
        await this.loadData();
    }

    async clearFilters() {
        this.state.filters = this.emptyFilters();
        await this.loadData();
    }

    formatCurrency(value) {
        return new Intl.NumberFormat("es-MX", {
            style: "currency",
            currency: this.state.data.currency || "MXN",
            maximumFractionDigits: 2,
        }).format(value || 0);
    }

    formatNumber(value) {
        return new Intl.NumberFormat("es-MX", {
            maximumFractionDigits: 2,
        }).format(value || 0);
    }

    formatMonth(key) {
        if (!key) {
            return "";
        }
        const [year, month] = key.split("-").map(Number);
        return new Intl.DateTimeFormat("es-MX", {
            month: "long",
            year: "numeric",
        }).format(new Date(year, month - 1, 1));
    }

    formatDate(value) {
        if (!value) {
            return "";
        }
        const [year, month, day] = value.split("-").map(Number);
        return new Intl.DateTimeFormat("es-MX", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
        }).format(new Date(year, month - 1, day));
    }

    segmentStyle(segment) {
        const percentage = Math.max(0, Math.min(100, segment.percentage || 0));
        return `width:${percentage}%;background-color:${segment.color};`;
    }

    accentStyle(item) {
        return `border-left-color:${item.color};`;
    }

    async openHistory() {
        await this.action.doAction(
            "mkp_collection_control.action_collection_line_history"
        );
    }

    async openDynamicAnalysis() {
        await this.action.doAction(
            "mkp_collection_control.action_collection_dashboard"
        );
    }

    async openUpcomingOrders() {
        const orderIds = this.state.data.upcoming?.order_ids || [];
        if (!orderIds.length) {
            this.notification.add(
                "No hay pedidos pendientes de pago para los filtros seleccionados.",
                { type: "info" }
            );
            return;
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Pedidos pendientes de pago",
            res_model: "sale.order",
            views: [[false, "list"], [false, "form"]],
            domain: [["id", "in", orderIds]],
            target: "current",
        });
    }
}

registry.category("actions").add(
    "mkp_collection_control.dashboard",
    MkpCollectionDashboard
);
