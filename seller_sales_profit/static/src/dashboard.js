/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
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
            salesAccountId: "",
            costAccountId: "",
            compareMonths: false,
            result: null,
            loading: false,
        });
        this.partnerActions = { create: false, createEdit: false, write: false };
        onWillStart(async () => {
            this.accounts = await this.orm.call(
                "account.move.line", "get_seller_sales_profit_accounts", []
            );
            const defaultAccount = (code) => {
                const account = this.accounts.find((item) => item.code === code);
                return account ? String(account.id) : "";
            };
            this.state.salesAccountId = defaultAccount("401.01.01");
            this.state.costAccountId = defaultAccount("501.01.01");
        });
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
                    Number(this.state.salesAccountId),
                    Number(this.state.costAccountId),
                    this.state.compareMonths,
                ]
            );
        } finally {
            this.state.loading = false;
        }
    }

    get pieStyle() {
        const { sales, cost, profit } = this.state.result;
        if (sales <= 0 || cost < 0 || profit < 0 || cost > sales) {
            return false;
        }
        const costPercent = (cost / sales) * 100;
        return `background: conic-gradient(#526a87 0% ${costPercent}%, #168064 ${costPercent}% 100%); width: 11rem; height: 11rem;`;
    }

    monthLabel(month) {
        return DateTime.fromISO(month).setLocale("es").toFormat("LLL yyyy");
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
