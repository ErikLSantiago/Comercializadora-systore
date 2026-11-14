from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    seller_sales_profit_enabled = fields.Boolean(
        string="Seller",
        help="Incluye este contacto en el selector del tablero de comisiones por ventas.",
        index=True,
    )
