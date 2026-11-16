from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


SALES_ACCOUNT_TYPE = "income"
COST_ACCOUNT_TYPE = "expense_direct_cost"


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.model
    def _seller_sales_profit_company_id(self):
        value = self.env["ir.config_parameter"].sudo().get_param(
            "seller_sales_profit.company_id", ""
        )
        return int(value) if value and value.isascii() and value.isdecimal() else False

    @api.model
    def _check_seller_sales_profit_access(self):
        if not self.env.user.has_group("account.group_account_readonly"):
            raise AccessError(_("Necesitas acceso de lectura a Contabilidad."))
        if self.env.company.id != self._seller_sales_profit_company_id():
            raise AccessError(_("El tablero solo está disponible en la empresa configurada."))

    @api.model
    def get_seller_sales_profit(
        self, partner_id, date_from, date_to, compare_periods=False
    ):
        self._check_seller_sales_profit_access()

        if type(partner_id) is not int or partner_id <= 0:
            raise ValidationError(_("Selecciona un seller."))
        partner = self.env["res.partner"].search(
            [("id", "=", partner_id), ("seller_sales_profit_enabled", "=", True)],
            limit=1,
        )
        if not partner:
            raise ValidationError(_("Selecciona un contacto con la casilla Es un seller activada."))

        try:
            date_from = fields.Date.to_date(date_from)
            date_to = fields.Date.to_date(date_to)
        except (TypeError, ValueError) as error:
            raise ValidationError(_("Ingresa fechas válidas.")) from error
        if not date_from or not date_to or date_from > date_to:
            raise ValidationError(_("Ingresa un periodo válido."))

        if compare_periods:
            date_to = date_from.replace(month=12, day=31)
            date_from = date_from.replace(month=1, day=1)

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
            base_domain, "401.01.01", SALES_ACCOUNT_TYPE, ["out_invoice", "out_refund"]
        )
        cost_domain = self._seller_sales_profit_domain(
            base_domain, "501.01.01", COST_ACCOUNT_TYPE, ["in_invoice", "in_refund"]
        )
        if compare_periods:
            sales_by_month = self._seller_sales_profit_month_balances(sales_domain)
            cost_by_month = self._seller_sales_profit_month_balances(cost_domain)
            return {
                "year": date_from.year,
                "currency_id": currency.id,
                "months": [
                    {
                        "month": month,
                        "sales": currency.round(-sales_by_month.get(month, 0.0)),
                        "profit": currency.round(
                            -sales_by_month.get(month, 0.0) - cost_by_month.get(month, 0.0)
                        ),
                    }
                    for month in range(1, 13)
                ],
            }

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
            "sales_count": sales_count,
            "cost_count": cost_count,
            "sales_domain": sales_domain,
            "cost_domain": cost_domain,
        }

    @api.model
    def _seller_sales_profit_domain(self, base_domain, account_code, account_type, move_types):
        accounts = self.env["account.account"]
        account = accounts.search(
            [
                *accounts._check_company_domain(self.env.company),
                ("code", "=", account_code),
                ("account_type", "=", account_type),
            ],
            limit=1,
        )
        if not account:
            raise ValidationError(_(
                "La cuenta %(code)s debe existir en la empresa activa con el tipo contable requerido.",
                code=account_code,
            ))
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
    def _seller_sales_profit_month_balances(self, domain):
        return {
            month.month: balance or 0.0
            for month, balance in self._read_group(domain, ["date:month"], ["balance:sum"])
        }
