from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


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
        string="Monto total a pagar (MXN)",
        currency_field="systore_company_currency_id",
        compute="_compute_systore_payment_obligations",
        store=True,
        help=(
            "Monto operativo contra el que se aplican los pagos manuales. "
            "No genera movimientos contables."
        ),
    )
    systore_amount_paid_mxn = fields.Monetary(
        string="Pagado (MXN)",
        currency_field="systore_company_currency_id",
        compute="_compute_systore_payment_totals",
        store=True,
    )
    systore_amount_pending_mxn = fields.Monetary(
        string="Pendiente (MXN)",
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
            ("paid", "Pagada"),
        ],
        string="Estado de pago",
        required=True,
        default="automatic",
        tracking=True,
        help=(
            "Permite cerrar manualmente la deuda. Al elegir Pagada, la orden "
            "deja de aportar saldos pendientes al tablero."
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
        string="Pagado (USD)",
        compute="_compute_systore_payment_totals",
        store=True,
        digits=(16, 2),
    )
    systore_amount_pending_usd = fields.Float(
        string="Pendiente (USD)",
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
                payable_mxn = (
                    (merchandise_usd + shipping_usd) * (order.x_exchange_rate or 0.0)
                    + import_mxn
                )
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
            usd_payments = payments.filtered(lambda item: item.payment_currency == "usd")
            paid_mxn = sum(payments.mapped("amount_mxn"))
            paid_usd = sum(usd_payments.mapped("amount_usd"))
            paid_mxn_usd = sum(usd_payments.mapped("amount_mxn"))
            effective_rate = paid_mxn_usd / paid_usd if paid_usd else 0.0
            merchandise = usd_payments.filtered(lambda item: item.concept == "merchandise")
            shipping = usd_payments.filtered(lambda item: item.concept == "shipping")
            import_payments = payments.filtered(
                lambda item: item.concept == "import" and item.payment_currency == "mxn"
            )
            merchandise_paid = sum(merchandise.mapped("amount_usd"))
            shipping_paid = sum(shipping.mapped("amount_usd"))
            import_paid = sum(import_payments.mapped("amount_mxn"))
            merchandise_pending = max(
                order.systore_merchandise_payable_usd - merchandise_paid, 0.0
            )
            shipping_pending = max(
                order.systore_shipping_payable_usd - shipping_paid, 0.0
            )
            import_pending = max(order.systore_import_payable_mxn - import_paid, 0.0)

            if order.systore_is_international:
                merchandise_rate = (
                    sum(merchandise.mapped("amount_mxn")) / merchandise_paid
                    if merchandise_paid else (order.x_exchange_rate or 0.0)
                )
                shipping_rate = (
                    sum(shipping.mapped("amount_mxn")) / shipping_paid
                    if shipping_paid else (order.x_exchange_rate or 0.0)
                )
                pending_mxn = (
                    merchandise_pending * merchandise_rate
                    + shipping_pending * shipping_rate
                    + import_pending
                )
                has_payment = paid_usd > 0 or import_paid > 0
                has_pending = (
                    merchandise_pending >= 0.01
                    or shipping_pending >= 0.01
                    or import_pending >= (order.company_id.currency_id.rounding or 0.01)
                )
            else:
                pending_mxn = max(order.systore_amount_payable_mxn - paid_mxn, 0.0)
                has_payment = paid_mxn > 0
                has_pending = pending_mxn >= (order.company_id.currency_id.rounding or 0.01)

            order.systore_amount_paid_mxn = paid_mxn
            order.systore_amount_pending_mxn = pending_mxn
            order.systore_amount_paid_usd = paid_usd
            order.systore_amount_pending_usd = merchandise_pending + shipping_pending
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
                order.systore_shipping_pending_usd = 0.0
                order.systore_import_pending_mxn = 0.0
                status = "paid"
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
        shipping_paid_mxn = sum(self.systore_payment_line_ids.filtered(
            lambda item: item.concept == "shipping" and item.payment_currency == "usd"
        ).mapped("amount_mxn"))
        shipping_rate = (
            shipping_paid_mxn / self.systore_shipping_paid_usd
            if self.systore_shipping_paid_usd else (self.x_exchange_rate or 0.0)
        )
        components = []
        if self.systore_merchandise_pending_usd > 0:
            components.append({
                "partner": self.partner_id,
                "concept": "merchandise",
                "paid_usd": self.systore_merchandise_paid_usd,
                "paid_mxn": merchandise_paid_mxn,
                "pending_usd": self.systore_merchandise_pending_usd,
                "pending_mxn": self.systore_merchandise_pending_usd * merchandise_rate,
            })
        if self.systore_shipping_pending_usd > 0:
            components.append({
                "partner": self.company_id.x_vendor_shipping_id,
                "concept": "shipping",
                "paid_usd": self.systore_shipping_paid_usd,
                "paid_mxn": shipping_paid_mxn,
                "pending_usd": self.systore_shipping_pending_usd,
                "pending_mxn": self.systore_shipping_pending_usd * shipping_rate,
            })
        if self.systore_import_pending_mxn > 0:
            components.append({
                "partner": self.company_id.x_vendor_import_id,
                "concept": "import",
                "paid_usd": 0.0,
                "paid_mxn": self.systore_import_paid_mxn,
                "pending_usd": 0.0,
                "pending_mxn": self.systore_import_pending_mxn,
            })
        return [item for item in components if item["partner"]]

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
            "domain": [("purchase_order_id", "=", self.id)],
            "context": {
                "default_purchase_order_id": self.id,
                "default_partner_id": self.partner_id.id,
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
