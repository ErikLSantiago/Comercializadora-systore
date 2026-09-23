from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SystorePurchasePayment(models.Model):
    _name = "systore.purchase.payment"
    _description = "Pago manual de compra"
    _order = "payment_date desc, id desc"

    purchase_order_id = fields.Many2one(
        "purchase.order",
        string="Orden de compra",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="purchase_order_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    payment_date = fields.Date(
        string="Fecha",
        required=True,
        default=fields.Date.context_today,
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Beneficiario",
        required=True,
    )
    concept = fields.Selection(
        [
            ("merchandise", "Mercancía"),
            ("shipping", "Logística / Envío"),
            ("import", "Importación"),
            ("other", "Otro"),
        ],
        string="Concepto",
        required=True,
        default="merchandise",
    )
    payment_currency = fields.Selection(
        [("mxn", "MXN"), ("usd", "USD")],
        string="Moneda del abono",
        required=True,
        default="mxn",
    )
    amount_usd = fields.Float(string="Monto pagado (USD)", digits=(16, 2))
    exchange_rate = fields.Float(
        string="Tipo de cambio USD/MXN",
        digits=(16, 4),
    )
    amount_mxn = fields.Monetary(
        string="Monto pagado (MXN)",
        currency_field="currency_id",
        required=True,
    )
    reference = fields.Char(string="Referencia")
    notes = fields.Text(string="Notas")

    @api.onchange("purchase_order_id", "concept")
    def _onchange_purchase_or_concept(self):
        for payment in self:
            order = payment.purchase_order_id
            if not order:
                continue
            if payment.concept == "shipping" and order.company_id.x_vendor_shipping_id:
                payment.partner_id = order.company_id.x_vendor_shipping_id
            elif payment.concept == "import" and order.company_id.x_vendor_import_id:
                payment.partner_id = order.company_id.x_vendor_import_id
            else:
                payment.partner_id = order.partner_id
            is_usd = (
                order._systore_resolved_purchase_origin() == "international"
                and payment.concept in ("merchandise", "shipping")
            )
            payment.payment_currency = "usd" if is_usd else "mxn"
            if is_usd and payment.exchange_rate <= 0:
                payment.exchange_rate = order.x_exchange_rate or 0.0
            elif not is_usd:
                payment.amount_usd = 0.0
                payment.exchange_rate = 0.0

    @api.onchange("payment_currency", "amount_usd", "exchange_rate")
    def _onchange_usd_amount(self):
        for payment in self:
            if payment.payment_currency == "usd":
                payment.amount_mxn = (
                    (payment.amount_usd or 0.0) * (payment.exchange_rate or 0.0)
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("payment_currency") == "usd":
                vals["amount_mxn"] = (
                    (vals.get("amount_usd") or 0.0)
                    * (vals.get("exchange_rate") or 0.0)
                )
        return super().create(vals_list)

    def write(self, vals):
        usd_fields = {"payment_currency", "amount_usd", "exchange_rate"}
        if not usd_fields.intersection(vals):
            return super().write(vals)
        result = True
        for payment in self:
            line_vals = dict(vals)
            currency = line_vals.get("payment_currency", payment.payment_currency)
            if currency == "usd":
                amount_usd = line_vals.get("amount_usd", payment.amount_usd) or 0.0
                rate = line_vals.get("exchange_rate", payment.exchange_rate) or 0.0
                line_vals["amount_mxn"] = amount_usd * rate
            result = super(SystorePurchasePayment, payment).write(line_vals) and result
        return result

    @api.constrains("payment_currency", "amount_usd", "exchange_rate", "amount_mxn")
    def _check_amount_mxn(self):
        for payment in self:
            if payment.payment_currency == "usd":
                if payment.amount_usd <= 0:
                    raise ValidationError("El monto pagado en USD debe ser mayor a cero.")
                if payment.exchange_rate <= 0:
                    raise ValidationError("El tipo de cambio debe ser mayor a cero.")
            if payment.amount_mxn <= 0:
                raise ValidationError("El monto pagado debe ser mayor a cero.")

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    systore_payment_line_ids = fields.One2many(
        "systore.purchase.payment",
        "purchase_order_id",
        string="Pagos manuales",
        copy=False,
    )
    systore_company_currency_id = fields.Many2one(
        related="company_id.currency_id",
        readonly=True,
    )
    systore_amount_payable_mxn = fields.Monetary(
        string="Monto proveedor a pagar (MXN)",
        currency_field="systore_company_currency_id",
        compute="_compute_systore_payment_obligations",
        store=True,
        help=(
            "Monto operativo contra el que se aplican los pagos manuales. "
            "No genera movimientos contables."
        ),
    )
    systore_amount_paid_mxn = fields.Monetary(
        string="Pagado al proveedor (MXN)",
        currency_field="systore_company_currency_id",
        compute="_compute_systore_payment_totals",
        store=True,
    )
    systore_amount_pending_mxn = fields.Monetary(
        string="Pendiente con proveedor (MXN)",
        currency_field="systore_company_currency_id",
        compute="_compute_systore_payment_totals",
        store=True,
    )
    systore_payment_status = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("partial", "Parcial"),
            ("paid", "Pagada"),
        ],
        string="Estado efectivo de pago",
        compute="_compute_systore_payment_totals",
        store=True,
        index=True,
    )
    systore_payment_status_manual = fields.Selection(
        [
            ("automatic", "Automático según abonos"),
            ("pending", "Pendiente"),
            ("partial", "Parcial"),
            ("paid", "Pagada"),
        ],
        string="Estado efectivo de pago",
        required=True,
        default="automatic",
        tracking=True,
        help=(
            "Permite usar el estado calculado por los abonos o fijar manualmente "
            "la orden como Pendiente, Parcial o Pagada."
        ),
    )
    systore_is_international = fields.Boolean(
        string="Compra internacional",
        compute="_compute_systore_payment_obligations",
        store=True,
    )
    systore_merchandise_payable_usd = fields.Float(
        string="Mercancía por pagar (USD)",
        compute="_compute_systore_payment_obligations",
        store=True,
        digits=(16, 2),
    )
    systore_shipping_payable_usd = fields.Float(
        string="Logística por pagar (USD)",
        compute="_compute_systore_payment_obligations",
        store=True,
        digits=(16, 2),
    )
    systore_import_payable_mxn = fields.Monetary(
        string="Importación por pagar (MXN)",
        currency_field="systore_company_currency_id",
        compute="_compute_systore_payment_obligations",
        store=True,
    )
    systore_amount_paid_usd = fields.Float(
        string="Pagado al proveedor (USD)",
        compute="_compute_systore_payment_totals",
        store=True,
        digits=(16, 2),
    )
    systore_amount_pending_usd = fields.Float(
        string="Pendiente con proveedor (USD)",
        compute="_compute_systore_payment_totals",
        store=True,
        digits=(16, 2),
    )
    systore_effective_exchange_rate = fields.Float(
        string="TC efectivo ponderado",
        compute="_compute_systore_payment_totals",
        store=True,
        digits=(16, 4),
    )
    systore_merchandise_paid_usd = fields.Float(
        compute="_compute_systore_payment_totals", store=True, digits=(16, 2)
    )
    systore_merchandise_pending_usd = fields.Float(
        compute="_compute_systore_payment_totals", store=True, digits=(16, 2)
    )
    systore_shipping_paid_usd = fields.Float(
        compute="_compute_systore_payment_totals", store=True, digits=(16, 2)
    )
    systore_shipping_pending_usd = fields.Float(
        compute="_compute_systore_payment_totals", store=True, digits=(16, 2)
    )
    systore_import_paid_mxn = fields.Monetary(
        currency_field="systore_company_currency_id",
        compute="_compute_systore_payment_totals",
        store=True,
    )
    systore_import_pending_mxn = fields.Monetary(
        currency_field="systore_company_currency_id",
        compute="_compute_systore_payment_totals",
        store=True,
    )
    systore_purchase_origin = fields.Selection(
        [
            ("auto", "Detección automática"),
            ("national", "Nacional"),
            ("international", "Internacional"),
        ],
        string="Origen de compra",
        default="auto",
        required=True,
        tracking=True,
    )
    systore_purchase_condition = fields.Selection(
        [
            ("undefined", "Sin definir"),
            ("cash", "Contado"),
            ("credit", "Crédito"),
        ],
        string="Condición de compra",
        required=True,
        default="undefined",
        tracking=True,
        index=True,
        help="Define si esta orden consume o no la línea de crédito del proveedor.",
    )
    systore_credit_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda del crédito",
        copy=True,
        tracking=True,
    )
    systore_credit_days = fields.Integer(
        string="Días de crédito",
        compute="_compute_systore_credit_days",
        store=True,
        help="Días naturales entre el inicio y el vencimiento del crédito.",
    )
    systore_credit_start_date = fields.Date(
        string="Inicio de crédito",
        copy=False,
        tracking=True,
        index=True,
    )
    systore_credit_due_date = fields.Date(
        string="Vencimiento crédito",
        copy=False,
        tracking=True,
        index=True,
    )
    systore_credit_amount = fields.Monetary(
        string="Monto sujeto a crédito",
        currency_field="systore_credit_currency_id",
        compute="_compute_systore_credit_amounts",
        store=True,
    )
    systore_credit_paid = fields.Monetary(
        string="Abonado al crédito",
        currency_field="systore_credit_currency_id",
        compute="_compute_systore_credit_amounts",
        store=True,
    )
    systore_credit_balance = fields.Monetary(
        string="Saldo que consume crédito",
        currency_field="systore_credit_currency_id",
        compute="_compute_systore_credit_amounts",
        store=True,
    )
    systore_credit_status = fields.Selection(
        [
            ("not_applicable", "No aplica"),
            ("not_started", "Crédito por iniciar"),
            ("active", "Vigente"),
            ("overdue", "Vencido"),
            ("paid", "Pagado"),
        ],
        string="Estado del crédito",
        compute="_compute_systore_credit_status",
    )

    @api.model
    def _systore_credit_defaults_from_partner(self, partner):
        if not partner:
            return {"systore_purchase_condition": "undefined"}
        if not partner.systore_supplier_credit_enabled:
            return {"systore_purchase_condition": "cash"}
        return {
            "systore_purchase_condition": "undefined",
            "systore_credit_currency_id": (
                partner.systore_supplier_credit_currency_id.id
                if partner.systore_supplier_credit_currency_id else False
            ),
        }

    @api.onchange("partner_id")
    def _onchange_systore_credit_partner(self):
        for order in self:
            defaults = order._systore_credit_defaults_from_partner(order.partner_id)
            for field_name, value in defaults.items():
                order[field_name] = value

    @api.onchange("systore_purchase_condition")
    def _onchange_systore_purchase_condition(self):
        for order in self:
            if order.systore_purchase_condition != "credit":
                continue
            partner = order.partner_id
            if partner and not order.systore_credit_currency_id:
                order.systore_credit_currency_id = (
                    partner.systore_supplier_credit_currency_id
                    or order.company_id.currency_id
                )

    @api.model_create_multi
    def create(self, vals_list):
        Partner = self.env["res.partner"]
        prepared = []
        for values in vals_list:
            vals = dict(values)
            if vals.get("partner_id") and not vals.get("systore_purchase_condition"):
                defaults = self._systore_credit_defaults_from_partner(
                    Partner.browse(vals["partner_id"])
                )
                defaults.update(vals)
                vals = defaults
            prepared.append(vals)
        return super().create(prepared)

    @api.depends("systore_credit_start_date", "systore_credit_due_date")
    def _compute_systore_credit_days(self):
        for order in self:
            if order.systore_credit_start_date and order.systore_credit_due_date:
                order.systore_credit_days = (
                    order.systore_credit_due_date - order.systore_credit_start_date
                ).days
            else:
                order.systore_credit_days = 0

    def _systore_convert_credit_amount(self, amount, source_currency, target_currency):
        self.ensure_one()
        if not amount or not source_currency or not target_currency:
            return 0.0
        if source_currency == target_currency:
            return amount
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        company_currency = self.company_id.currency_id
        exchange_rate = self.x_exchange_rate or 0.0
        if usd and exchange_rate:
            if source_currency == usd and target_currency == company_currency:
                return amount * exchange_rate
            if source_currency == company_currency and target_currency == usd:
                return amount / exchange_rate
        conversion_date = fields.Date.to_date(self.date_order) or fields.Date.context_today(self)
        return source_currency._convert(
            amount, target_currency, self.company_id, conversion_date
        )

    @api.depends(
        "systore_purchase_condition",
        "systore_credit_currency_id",
        "systore_is_international",
        "systore_merchandise_payable_usd",
        "systore_merchandise_paid_usd",
        "systore_merchandise_pending_usd",
        "systore_amount_payable_mxn",
        "systore_amount_paid_mxn",
        "systore_amount_pending_mxn",
        "systore_payment_status_manual",
        "x_exchange_rate",
    )
    def _compute_systore_credit_amounts(self):
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        for order in self:
            amount = paid = balance = 0.0
            target_currency = order.systore_credit_currency_id
            if order.systore_purchase_condition == "credit" and target_currency:
                if order.systore_is_international and usd:
                    source_currency = usd
                    source_amount = order.systore_merchandise_payable_usd
                    source_paid = order.systore_merchandise_paid_usd
                    source_balance = order.systore_merchandise_pending_usd
                else:
                    source_currency = order.company_id.currency_id
                    source_amount = order.systore_amount_payable_mxn
                    source_paid = order.systore_amount_paid_mxn
                    source_balance = order.systore_amount_pending_mxn
                amount = order._systore_convert_credit_amount(
                    source_amount, source_currency, target_currency
                )
                paid = order._systore_convert_credit_amount(
                    source_paid, source_currency, target_currency
                )
                balance = order._systore_convert_credit_amount(
                    source_balance, source_currency, target_currency
                )
            order.systore_credit_amount = amount
            order.systore_credit_paid = min(paid, amount) if amount else 0.0
            order.systore_credit_balance = min(balance, amount) if amount else 0.0

    def _systore_credit_balance_in_currency(self, currency):
        self.ensure_one()
        return self._systore_convert_credit_amount(
            self.systore_credit_balance,
            self.systore_credit_currency_id,
            currency,
        )

    @api.depends(
        "systore_purchase_condition",
        "systore_credit_start_date",
        "systore_credit_due_date",
        "systore_credit_amount",
        "systore_credit_balance",
        "systore_payment_status",
    )
    def _compute_systore_credit_status(self):
        today = fields.Date.context_today(self)
        for order in self:
            start_date = order.systore_credit_start_date
            due_date = order.systore_credit_due_date
            if order.systore_purchase_condition != "credit":
                status = "not_applicable"
            elif order.systore_payment_status == "paid" or (
                order.systore_credit_amount > 0 and order.systore_credit_balance <= 0
            ):
                status = "paid"
            elif not start_date or not due_date or today < start_date:
                status = "not_started"
            elif due_date < today:
                status = "overdue"
            else:
                status = "active"
            order.systore_credit_status = status

    @api.constrains("systore_credit_start_date", "systore_credit_due_date")
    def _check_systore_credit_dates(self):
        for order in self:
            if (
                order.systore_credit_start_date
                and order.systore_credit_due_date
                and order.systore_credit_due_date < order.systore_credit_start_date
            ):
                raise ValidationError(
                    "El vencimiento del crédito no puede ser anterior a su inicio."
                )

    def button_confirm(self):
        for order in self:
            if order.systore_purchase_condition == "undefined":
                raise UserError(_(
                    "Define si la orden %s es una compra de Contado o a Crédito."
                ) % order.name)
            if order.systore_purchase_condition == "credit":
                if not order.systore_credit_currency_id:
                    raise UserError(_("Selecciona la moneda del crédito."))
                if not order.systore_credit_start_date:
                    raise UserError(_("Captura el inicio del crédito."))
                if not order.systore_credit_due_date:
                    raise UserError(_("Captura el vencimiento del crédito."))
        return super().button_confirm()

    @api.depends(
        "systore_purchase_origin",
        "amount_total",
        "x_exchange_rate",
        "order_line.product_qty",
        "order_line.x_gross_usd",
        "order_line.x_ship_usd",
        "order_line.x_import_mxn",
    )
    def _compute_systore_payment_obligations(self):
        for order in self:
            international = order._systore_resolved_purchase_origin() == "international"
            merchandise_usd = shipping_usd = import_mxn = 0.0
            if international:
                for line in order.order_line.filtered(lambda item: not item.display_type):
                    qty = line.product_qty or 0.0
                    merchandise_usd += qty * (line.x_gross_usd or 0.0)
                    shipping_usd += qty * (line.x_ship_usd or 0.0)
                    import_mxn += qty * (line.x_import_mxn or 0.0)
                payable_mxn = merchandise_usd * (order.x_exchange_rate or 0.0)
            else:
                payable_mxn = order.amount_total or 0.0
            order.systore_is_international = international
            order.systore_merchandise_payable_usd = merchandise_usd
            order.systore_shipping_payable_usd = shipping_usd
            order.systore_import_payable_mxn = import_mxn
            order.systore_amount_payable_mxn = payable_mxn

    @api.depends(
        "systore_amount_payable_mxn",
        "systore_merchandise_payable_usd",
        "systore_shipping_payable_usd",
        "systore_import_payable_mxn",
        "systore_payment_status_manual",
        "x_exchange_rate",
        "systore_payment_line_ids.concept",
        "systore_payment_line_ids.payment_currency",
        "systore_payment_line_ids.amount_usd",
        "systore_payment_line_ids.exchange_rate",
        "systore_payment_line_ids.amount_mxn",
    )
    def _compute_systore_payment_totals(self):
        for order in self:
            payments = order.systore_payment_line_ids
            merchandise_payments = payments.filtered(
                lambda item: item.concept == "merchandise"
            )
            merchandise = merchandise_payments.filtered(
                lambda item: item.payment_currency == "usd"
            )
            shipping = payments.filtered(
                lambda item: (
                    item.concept == "shipping" and item.payment_currency == "usd"
                )
            )
            import_payments = payments.filtered(
                lambda item: item.concept == "import" and item.payment_currency == "mxn"
            )
            merchandise_paid = sum(merchandise.mapped("amount_usd"))
            merchandise_paid_mxn = sum(merchandise.mapped("amount_mxn"))
            national_paid_mxn = sum(merchandise_payments.mapped("amount_mxn"))
            shipping_paid = sum(shipping.mapped("amount_usd"))
            import_paid = sum(import_payments.mapped("amount_mxn"))
            effective_rate = (
                merchandise_paid_mxn / merchandise_paid
                if merchandise_paid else 0.0
            )
            merchandise_pending = max(
                order.systore_merchandise_payable_usd - merchandise_paid, 0.0
            )
            shipping_pending = max(
                order.systore_shipping_payable_usd - shipping_paid, 0.0
            )
            import_pending = max(order.systore_import_payable_mxn - import_paid, 0.0)

            if order.systore_is_international:
                merchandise_rate = (
                    effective_rate or order.x_exchange_rate or 0.0
                )
                paid_mxn = merchandise_paid_mxn
                paid_usd = merchandise_paid
                pending_mxn = merchandise_pending * merchandise_rate
                pending_usd = merchandise_pending
                has_payment = merchandise_paid > 0
                has_pending = merchandise_pending >= 0.01
            else:
                paid_mxn = national_paid_mxn
                paid_usd = 0.0
                pending_mxn = max(order.systore_amount_payable_mxn - paid_mxn, 0.0)
                pending_usd = 0.0
                has_payment = paid_mxn > 0
                has_pending = pending_mxn >= (order.company_id.currency_id.rounding or 0.01)

            order.systore_amount_paid_mxn = paid_mxn
            order.systore_amount_pending_mxn = pending_mxn
            order.systore_amount_paid_usd = paid_usd
            order.systore_amount_pending_usd = pending_usd
            order.systore_effective_exchange_rate = effective_rate
            order.systore_merchandise_paid_usd = merchandise_paid
            order.systore_merchandise_pending_usd = merchandise_pending
            order.systore_shipping_paid_usd = shipping_paid
            order.systore_shipping_pending_usd = shipping_pending
            order.systore_import_paid_mxn = import_paid
            order.systore_import_pending_mxn = import_pending
            manual_status = order.systore_payment_status_manual
            if manual_status == "paid":
                order.systore_amount_pending_mxn = 0.0
                order.systore_amount_pending_usd = 0.0
                order.systore_merchandise_pending_usd = 0.0
                status = "paid"
            elif manual_status in ("pending", "partial"):
                status = manual_status
            elif not has_payment:
                status = "pending"
            elif has_pending:
                status = "partial"
            else:
                status = "paid"
            order.systore_payment_status = status

    def _systore_debt_components(self):
        self.ensure_one()
        if not self.systore_is_international:
            return [{
                "partner": self.partner_id,
                "concept": "merchandise",
                "paid_usd": 0.0,
                "paid_mxn": self.systore_amount_paid_mxn,
                "pending_usd": 0.0,
                "pending_mxn": self.systore_amount_pending_mxn,
            }] if self.systore_amount_pending_mxn > 0 else []

        merchandise_paid_mxn = sum(self.systore_payment_line_ids.filtered(
            lambda item: item.concept == "merchandise" and item.payment_currency == "usd"
        ).mapped("amount_mxn"))
        merchandise_rate = (
            merchandise_paid_mxn / self.systore_merchandise_paid_usd
            if self.systore_merchandise_paid_usd else (self.x_exchange_rate or 0.0)
        )
        if self.systore_merchandise_pending_usd > 0:
            return [{
                "partner": self.partner_id,
                "concept": "merchandise",
                "paid_usd": self.systore_merchandise_paid_usd,
                "paid_mxn": merchandise_paid_mxn,
                "pending_usd": self.systore_merchandise_pending_usd,
                "pending_mxn": self.systore_merchandise_pending_usd * merchandise_rate,
            }]
        return []

    def action_systore_open_payments(self):
        self.ensure_one()
        list_view = self.env.ref(
            "systore_purchase_supply_dashboard.view_purchase_payment_list"
        )
        form_view = self.env.ref(
            "systore_purchase_supply_dashboard.view_purchase_payment_form"
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Abonos de %s") % self.name,
            "res_model": "systore.purchase.payment",
            "view_mode": "list,form",
            "views": [(list_view.id, "list"), (form_view.id, "form")],
            "domain": [
                ("purchase_order_id", "=", self.id),
                ("concept", "=", "merchandise"),
            ],
            "context": {
                "default_purchase_order_id": self.id,
                "default_partner_id": self.partner_id.id,
                "default_concept": "merchandise",
                "default_payment_currency": (
                    "usd" if self._systore_resolved_purchase_origin() == "international"
                    else "mxn"
                ),
                "default_exchange_rate": self.x_exchange_rate or 0.0,
            },
            "target": "current",
        }

    def _systore_resolved_purchase_origin(self):
        self.ensure_one()
        if self.systore_purchase_origin != "auto":
            return self.systore_purchase_origin
        has_usd = any(
            (line.x_gross_usd or 0.0) > 0 or (line.x_ship_usd or 0.0) > 0
            for line in self.order_line.filtered(lambda line: not line.display_type)
        )
        return "international" if has_usd else "national"

    def _systore_line_cost_mxn(self, line):
        """Return the operational landed unit cost in company currency."""
        self.ensure_one()
        if self._systore_resolved_purchase_origin() == "international":
            return line.x_calc_price_mxn or 0.0
        order_currency = self.currency_id
        company_currency = self.company_id.currency_id
        price = line.price_unit or 0.0
        if order_currency == company_currency:
            return price
        conversion_date = fields.Date.to_date(self.date_order) or fields.Date.context_today(self)
        return order_currency._convert(price, company_currency, self.company_id, conversion_date)

    def _systore_total_cost_mxn(self):
        self.ensure_one()
        return sum(
            (line.product_qty or 0.0) * self._systore_line_cost_mxn(line)
            for line in self.order_line.filtered(lambda line: not line.display_type)
        )
