from odoo import fields, models


class SystoreSupplyDebtReport(models.TransientModel):
    _name = "systore.supply.debt.report"
    _description = "Deuda histórica a proveedores"
    _order = "debt_date desc, purchase_order_id desc, product_id"

    company_id = fields.Many2one("res.company", required=True, readonly=True)
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", readonly=True
    )
    usd_currency_id = fields.Many2one(
        "res.currency", string="Moneda USD", required=True, readonly=True
    )
    cutoff_date = fields.Date(string="Fecha de corte", required=True, readonly=True)
    debt_date = fields.Date(string="Fecha de deuda", required=True, readonly=True)
    debt_date_source = fields.Selection(
        [("order", "Fecha de orden"), ("receipt", "Fecha de llegada")],
        string="Origen de fecha",
        required=True,
        readonly=True,
    )
    sector = fields.Selection(
        [("national", "Nacional"), ("international", "Internacional")],
        string="Tipo de proveedor",
        required=True,
        readonly=True,
    )
    supplier_id = fields.Many2one(
        "res.partner", string="Proveedor", required=True, readonly=True
    )
    purchase_order_id = fields.Many2one(
        "purchase.order", string="Orden de compra", required=True, readonly=True
    )
    purchase_line_id = fields.Many2one(
        "purchase.order.line", string="Línea de compra", required=True, readonly=True
    )
    product_id = fields.Many2one(
        "product.product", string="Producto", required=True, readonly=True
    )
    internal_reference = fields.Char(
        string="Referencia interna", readonly=True
    )
    ordered_qty = fields.Float(
        string="Piezas ordenadas", readonly=True
    )
    received_qty = fields.Float(
        string="Piezas recibidas", readonly=True
    )
    pending_qty = fields.Float(
        string="Piezas faltantes", readonly=True
    )
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
