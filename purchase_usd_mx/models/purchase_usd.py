from odoo import api, fields, models

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    company_currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True, readonly=True
    )
    usd_currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_usd_currency_id",
        string="USD Currency",
        store=False,
    )
    usd_mx_rate = fields.Monetary(
        string="USD MX",
        currency_field="company_currency_id",
        help="Tipo de cambio MXN por 1 USD para esta orden.",
        default=1.0,
    )
    amount_total_usd = fields.Monetary(
        string="Total USD",
        currency_field="usd_currency_id",
        compute="_compute_amount_total_usd",
        store=False,
        help="Suma de Total USD en las líneas."
    )

    def _compute_usd_currency_id(self):
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        for order in self:
            order.usd_currency_id = usd

    @api.depends("order_line.total_usd")
    def _compute_amount_total_usd(self):
        for order in self:
            order.amount_total_usd = sum(order.order_line.mapped("total_usd"))

class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    usd_currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_usd_currency_id",
        store=False,
    )
    price_unit_usd = fields.Monetary(
        string="Precio USD",
        currency_field="usd_currency_id",
        compute="_compute_usd_amounts",
        store=False,
    )
    total_usd = fields.Monetary(
        string="Total USD",
        currency_field="usd_currency_id",
        compute="_compute_usd_amounts",
        store=False,
    )

    def _compute_usd_currency_id(self):
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        for line in self:
            line.usd_currency_id = usd

    @api.depends("price_unit", "product_qty", "order_id.usd_mx_rate")
    def _compute_usd_amounts(self):
        for line in self:
            rate = line.order_id.usd_mx_rate or 0.0
            if rate > 0:
                price_usd = line.price_unit / rate
                total_usd = price_usd * line.product_qty
            else:
                price_usd = 0.0
                total_usd = 0.0
            line.price_unit_usd = price_usd
            line.total_usd = total_usd