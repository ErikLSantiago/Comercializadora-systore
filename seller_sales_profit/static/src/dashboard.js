/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatMonetary } from "@web/views/fields/formatters";
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";

const { DateTime } = luxon;

class SellerSalesProfitDashboard extends Component {
    static template = "seller_sales_profit.Dashboard";
    static components = { Many2XAutocomplete };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        const today = DateTime.local();
        this.state = useState({
            sellerId: false,
            sellerName: "",
            dateFrom: today.startOf("month").toISODate(),
            dateTo: today.toISODate(),
            salesCode: "401.01.01",
            costCode: "501.01.01",
            result: null,
            loading: false,
        });
        this.partnerActions = { create: false, createEdit: false, write: false };
    }

    partnerDomain() {
        return [];
    }

    selectSeller(records) {
        const partner = records && records[0];
        this.state.sellerId = partner ? partner.id : false;
        this.state.sellerName = partner ? partner.display_name : "";
        this.clearResult();
    }

    clearResult() {
        this.state.result = null;
    }

    async load(event) {
        event.preventDefault();
        if (!this.state.sellerId || this.state.loading) {
            return;
        }
        this.state.loading = true;
        this.clearResult();
        try {
            this.state.result = await this.orm.call(
                "account.move.line",
                "get_seller_sales_profit",
                [
                    this.state.sellerId,
                    this.state.dateFrom,
                    this.state.dateTo,
                    this.state.salesCode,
                    this.state.costCode,
                ]
            );
        } finally {
            this.state.loading = false;
        }
    }

    money(value) {
        return formatMonetary(value, { currencyId: this.state.result.currency_id });
    }

    openLines(name, domain) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: "account.move.line",
            views: [[false, "list"], [false, "form"]],
            domain,
            target: "current",
            context: { create: false, edit: false, delete: false },
        });
    }
}

registry.category("actions").add("seller_sales_profit.dashboard", SellerSalesProfitDashboard);
