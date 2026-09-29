from odoo import fields, models


class SystoreSupplyDebtReport(models.TransientModel):
    _name = "systore.supply.debt.report"
    _description = "Deuda histórica a proveedores"
    _order = "balance_mxn desc, balance_usd desc, supplier_id"

    company_id = fields.Many2one("res.company", required=True, readonly=True)
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", readonly=True
    )
    usd_currency_id = fields.Many2one(
        "res.currency", string="Moneda USD", required=True, readonly=True
    )
    cutoff_date = fields.Date(string="Fecha de corte", required=True, readonly=True)
    sector = fields.Selection(
        [("national", "Nacional"), ("international", "Internacional")],
        string="Tipo de proveedor",
        required=True,
        readonly=True,
    )
    supplier_id = fields.Many2one(
        "res.partner", string="Proveedor", required=True, readonly=True
    )
    purchase_order_ids = fields.Many2many(
        "purchase.order",
        "systore_debt_report_purchase_rel",
        "report_id",
        "purchase_order_id",
        string="Órdenes de compra",
        readonly=True,
    )
    order_count = fields.Integer(string="Órdenes", readonly=True)
    effective_exchange_rate = fields.Float(
        string="TC efectivo USD/MXN", digits=(16, 4), readonly=True
    )

    total_usd = fields.Monetary(
        string="Monto de deuda USD",
        currency_field="usd_currency_id",
        readonly=True,
    )
    paid_usd = fields.Monetary(
        string="Pagado USD", currency_field="usd_currency_id", readonly=True
    )
    balance_usd = fields.Monetary(
        string="Saldo por pagar USD",
        currency_field="usd_currency_id",
        readonly=True,
    )
    total_mxn = fields.Monetary(
        string="Monto de deuda MXN", currency_field="currency_id", readonly=True
    )
    paid_mxn = fields.Monetary(
        string="Pagado MXN", currency_field="currency_id", readonly=True
    )
    balance_mxn = fields.Monetary(
        string="Saldo por pagar MXN", currency_field="currency_id", readonly=True
    )
