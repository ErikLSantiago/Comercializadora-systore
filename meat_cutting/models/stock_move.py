from odoo import fields, models

class StockMove(models.Model):
    _inherit = "stock.move"

    x_cutting_order_id = fields.Many2one("meat.cutting.order", string="Orden Despiece", index=True)
    x_weight_total_kg = fields.Float(string="Peso Total (kg)", digits="Product Unit of Measure")
