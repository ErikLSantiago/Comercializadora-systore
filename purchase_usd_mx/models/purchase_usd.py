from odoo import api, fields, models

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    usd_mx = fields.Monetary(
        string="USD MX",
        currency_field="currency_id",
        help="Tipo de cambio expresado en la moneda del pedido (MXN por 1 USD). "
             "Se usa para calcular los importes en USD.",
        default=1.0,
    )
    usd_currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_usd_currency",
        string="Moneda USD",
        store=False,
    )
    amount_total_usd = fields.Monetary(
        string="Total USD",
        currency_field="usd_currency_id",
        compute="_compute_amount_total_usd",
        store=False,
    )

    def _compute_usd_currency(self):
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        if not usd:
            usd = self.env["res.currency"].search([("name", "=", "USD")], limit=1)
        for order in self:
            order.usd_currency_id = usd or order.currency_id

    @api.depends("order_line.price_unit", "order_line.product_qty", "usd_mx")
    def _compute_amount_total_usd(self):
        for order in self:
            total = 0.0
            rate = order.usd_mx or 0.0
            if rate:
                for line in order.order_line:
                    total += (line.price_unit / rate) * line.product_qty
            order.amount_total_usd = total


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    usd_currency_id = fields.Many2one(
        "res.currency",
        related="order_id.usd_currency_id",
        store=False,
        readonly=True,
    )
    price_usd = fields.Monetary(
        string="Precio USD",
        currency_field="usd_currency_id",
        compute="_compute_usd_prices",
        store=False,
    )
    price_total_usd = fields.Monetary(
        string="Total USD",
        currency_field="usd_currency_id",
        compute="_compute_usd_prices",
        store=False,
    )

    @api.depends("price_unit", "product_qty", "order_id.usd_mx")
    def _compute_usd_prices(self):
        for line in self:
            rate = line.order_id.usd_mx or 0.0
            if rate:
                price_usd = line.price_unit / rate
                total_usd = price_usd * line.product_qty
            else:
                price_usd = 0.0
                total_usd = 0.0
            line.price_usd = price_usd
            line.price_total_usd = total_usd