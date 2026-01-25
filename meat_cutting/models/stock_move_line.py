from odoo import fields, models

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    x_weight_kg = fields.Float(string="Peso (kg)", digits="Product Unit of Measure")
