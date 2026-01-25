from odoo import fields, models

class StockLot(models.Model):
    _inherit = "stock.lot"

    x_weight_kg = fields.Float(string="Peso (kg)", digits="Product Unit of Measure")
    x_serial_code = fields.Char(string="Serial base", help="Código base del serial sin peso (ej. C-0001).")

    def name_get(self):
        return [(lot.id, lot.name or "") for lot in self]
