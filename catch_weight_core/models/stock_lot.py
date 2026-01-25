from odoo import fields, models

class StockLot(models.Model):
    _inherit = "stock.lot"

    x_weight_g = fields.Integer("Peso (g)", help="Peso exacto del lote en gramos para productos catch-weight.")
