from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


SALES_ACCOUNT_TYPE = "income"
COST_ACCOUNT_TYPE = "expense_direct_cost"


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.model
    def get_seller_sales_profit_accounts(self):
        self._check_seller_sales_profit_access()
        accounts = self.env["account.account"]
        return accounts.search_read(
            [
                *accounts._check_company_domain(self.env.company),
                ("account_type", "in", [SALES_ACCOUNT_TYPE, COST_ACCOUNT_TYPE]),
            ],
            ["name", "code", "account_type"],
            order="name, id",
        )

    @api.model
    def _check_seller_sales_profit_access(self):
        if not self.env.user.has_group("account.group_account_readonly"):
            raise AccessError(_("Necesitas acceso de lectura a Contabilidad."))

    @api.model
    def get_seller_sales_profit(
        self, partner_id, date_from, date_to, sales_account_id, cost_account_id, compare_months=False
    ):
        self._check_seller_sales_profit_access()

        if type(partner_id) is not int or partner_id <= 0:
            raise ValidationError(_("Selecciona un seller."))
        partner = self.env["res.partner"].search(
            [("id", "=", partner_id), ("seller_sales_profit_enabled", "=", True)],
            limit=1,
        )
        if not partner:
            raise ValidationError(_("Selecciona un contacto marcado como Seller."))

        try:
            date_from = fields.Date.to_date(date_from)
            date_to = fields.Date.to_date(date_to)
        except (TypeError, ValueError) as error:
            raise ValidationError(_("Ingresa fechas válidas.")) from error
        if not date_from or not date_to or date_from > date_to:
            raise ValidationError(_("Ingresa un periodo válido."))

        company = self.env.company
        currency = company.currency_id
        base_domain = [
            ("company_id", "=", company.id),
            ("move_id.state", "=", "posted"),
            ("move_id.commercial_partner_id", "=", partner.commercial_partner_id.id),
            ("date", ">=", fields.Date.to_string(date_from)),
            ("date", "<=", fields.Date.to_string(date_to)),
            ("tax_line_id", "=", False),
            ("display_type", "in", ["product", "discount", "rounding", "epd"]),
        ]
        sales_domain = self._seller_sales_profit_domain(
            base_domain, sales_account_id, SALES_ACCOUNT_TYPE, ["out_invoice", "out_refund"]
        )
        cost_domain = self._seller_sales_profit_domain(
            base_domain, cost_account_id, COST_ACCOUNT_TYPE, ["in_invoice", "in_refund"]
        )
        sales, sales_count = self._seller_sales_profit_total(sales_domain, -1)
        cost, cost_count = self._seller_sales_profit_total(cost_domain, 1)
        return {
            "seller": partner.commercial_partner_id.display_name,
            "company": company.display_name,
            "currency_id": currency.id,
            "currency_name": currency.name,
            "sales": currency.round(sales),
            "cost": currency.round(cost),
            "profit": currency.round(sales - cost),
            "months": self._seller_sales_profit_months(
                sales_domain, cost_domain, date_from, date_to, currency
            ) if compare_months else [],
            "sales_count": sales_count,
            "cost_count": cost_count,
            "sales_domain": sales_domain,
            "cost_domain": cost_domain,
        }

    @api.model
    def _seller_sales_profit_domain(self, base_domain, account_id, account_type, move_types):
        if type(account_id) is not int or account_id <= 0:
            raise ValidationError(_("Selecciona una cuenta contable."))
        accounts = self.env["account.account"]
        account = accounts.search(
            [
                *accounts._check_company_domain(self.env.company),
                ("id", "=", account_id),
                ("account_type", "=", account_type),
            ],
            limit=1,
        )
        if not account:
            raise ValidationError(_("La cuenta debe pertenecer a la compañía activa y tener el tipo contable requerido."))
        return base_domain + [
            ("account_id", "=", account.id),
            ("move_id.move_type", "in", move_types),
        ]

    @api.model
    def _seller_sales_profit_total(self, domain, sign):
        [(balance, line_count)] = self._read_group(
            domain, aggregates=["balance:sum", "__count"]
        )
        return sign * (balance or 0.0), line_count

    @api.model
    def _seller_sales_profit_months(self, sales_domain, cost_domain, date_from, date_to, currency):
        def month_balances(domain):
            rows = self._read_group(domain, ["date:month"], ["balance:sum"])
            return {month: balance or 0.0 for month, balance in rows}

        sales_by_month = month_balances(sales_domain)
        cost_by_month = month_balances(cost_domain)
        month = date_from.replace(day=1)
        last_month = date_to.replace(day=1)
        rows = []
        while month <= last_month:
            sales = -sales_by_month.get(month, 0.0)
            cost = cost_by_month.get(month, 0.0)
            rows.append({
                "month": fields.Date.to_string(month),
                "sales": currency.round(sales),
                "cost": currency.round(cost),
                "profit": currency.round(sales - cost),
            })
            if month == last_month:
                break
            month = fields.Date.add(month, months=1)
        return rows
