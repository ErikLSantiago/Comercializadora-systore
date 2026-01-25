from odoo import fields, models

class StockLot(models.Model):
    _inherit = "stock.lot"

    x_weight_kg = fields.Float(string="Peso (kg)", digits="Product Unit of Measure")

    def name_get(self):
        res = []
        for lot in self:
            if lot.x_weight_kg:
                # Formato: 0.200-KG-C-0001
                res.append((lot.id, f"{lot.x_weight_kg:.3f}-KG-{lot.name}"))
            else:
                res.append((lot.id, lot.name))
        return res
