/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { session } from "@web/session";
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
        this.company = useService("company");

        const today = DateTime.local();
        this.state = useState({
            sellerId: false,
            sellerName: "",
            year: today.year,
            month: String(today.month),
            dateFrom: today.startOf("month").toISODate(),
            dateTo: today.endOf("month").toISODate(),
            comparison: null,
            result: null,
            loading: false,
        });
        this.months = Array.from({ length: 12 }, (_, index) => ({
            number: index + 1,
            label: DateTime.fromObject({ year: 2000, month: index + 1 })
                .setLocale("es").toFormat("LLLL"),
        }));
        this.partnerActions = { create: false, createEdit: false, write: false };
    }

    get isEnabled() {
        return this.company.currentCompany.id === session.seller_sales_profit_company_id;
    }

    partnerDomain() {
        return [["seller_sales_profit_enabled", "=", true]];
    }

    selectSeller(records) {
        const partner = records && records[0];
        this.state.sellerId = partner ? partner.id : false;
        this.state.sellerName = partner ? partner.display_name : "";
        this.clearResult();
    }

    changeQuickPeriod(event) {
        if (event.target.name === "year") {
            this.state.year = event.target.value;
        } else {
            this.state.month = event.target.value;
        }
        if (event.target.name === "month" && !this.state.year) {
            this.state.year = DateTime.local().year;
        }
        const year = Number(this.state.year);
        if (!Number.isInteger(year) || year < 1 || year > 9999) {
            this.clearResult();
            return;
        }
        const month = Number(this.state.month);
        const start = DateTime.fromObject({ year, month: month || 1, day: 1 });
        this.state.dateFrom = start.toISODate();
        this.state.dateTo = start.endOf(month ? "month" : "year").toISODate();
        this.clearResult();
    }

    changeCustomPeriod() {
        this.state.year = "";
        this.state.month = "";
        this.clearResult();
    }

    clearResult() {
        this.state.result = null;
        this.state.comparison = null;
    }

    load(event) {
        event.preventDefault();
        return this.query();
    }

    shiftMonth(offset) {
        const reference = DateTime.fromISO(this.state.dateFrom || "");
        if (!reference.isValid) {
            return;
        }
        const start = reference.startOf("month").plus({ months: offset });
        if (start.year < 1 || start.year > 9999) {
            return;
        }
        this.state.year = start.year;
        this.state.month = String(start.month);
        this.state.dateFrom = start.toISODate();
        this.state.dateTo = start.endOf("month").toISODate();
        this.clearResult();
        return this.query();
    }

    async query(compare = false) {
        if (!this.isEnabled || !this.state.sellerId || this.state.loading) {
            return;
        }
        this.state.loading = true;
        if (!compare) {
            this.clearResult();
        }
        try {
            const result = await this.orm.call(
                "account.move.line",
                "get_seller_sales_profit",
                [this.state.sellerId, this.state.dateFrom, this.state.dateTo, compare]
            );
            if (compare) {
                this.state.comparison = result;
            } else {
                this.state.result = result;
            }
        } finally {
            this.state.loading = false;
        }
    }

    get comparisonScale() {
        const values = this.state.comparison.months.flatMap(({ sales, profit }) => [sales, profit]);
        const minimum = Math.min(0, ...values);
        const maximum = Math.max(0, ...values);
        return { minimum, span: maximum - minimum || 1 };
    }

    barStyle(value, scale) {
        const left = ((Math.min(value, 0) - scale.minimum) / scale.span) * 100;
        const width = (Math.abs(value) / scale.span) * 100;
        return `left: ${left}%; width: ${width}%;`;
    }

    get pieStyle() {
        const { sales, cost, profit } = this.state.result;
        if (sales <= 0 || cost < 0 || profit < 0 || cost > sales) {
            return false;
        }
        const costPercent = (cost / sales) * 100;
        return `background: conic-gradient(#526a87 0% ${costPercent}%, #168064 ${costPercent}% 100%); width: 11rem; height: 11rem;`;
    }

    money(value, currencyId = this.state.result.currency_id) {
        return formatMonetary(value, { currencyId });
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
