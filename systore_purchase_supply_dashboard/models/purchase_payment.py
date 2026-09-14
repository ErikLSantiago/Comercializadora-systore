from odoo import api, fields, models
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

    @api.constrains("amount_mxn")
    def _check_amount_mxn(self):
        for payment in self:
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
        copy=False,
        tracking=True,
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
        string="Estado de pago",
        compute="_compute_systore_payment_totals",
        store=True,
        index=True,
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
        "systore_amount_payable_mxn",
        "systore_payment_line_ids.amount_mxn",
    )
    def _compute_systore_payment_totals(self):
        for order in self:
            paid = sum(order.systore_payment_line_ids.mapped("amount_mxn"))
            payable = order.systore_amount_payable_mxn or 0.0
            pending = max(payable - paid, 0.0)
            order.systore_amount_paid_mxn = paid
            order.systore_amount_pending_mxn = pending
            rounding = order.company_id.currency_id.rounding or 0.01
            if paid <= 0:
                status = "pending"
            elif payable > 0 and pending >= rounding:
                status = "partial"
            else:
                status = "paid"
            order.systore_payment_status = status

    def action_systore_use_cost_as_payable(self):
        for order in self:
            order.systore_amount_payable_mxn = order._systore_total_cost_mxn()
        return True

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
