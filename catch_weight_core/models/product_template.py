from odoo import fields, models

class ProductTemplate(models.Model):
    _inherit = "product.template"

    x_is_catch_weight = fields.Boolean("Catch Weight (peso variable)", default=False)
    x_is_waste = fields.Boolean(
        "Es merma",
        default=False,
        help="Marcar para identificar productos usados como merma/recorte en el wizard de cierre de producción.",
    )
    x_shelf_life_days = fields.Integer("Vida útil (días)", default=0, help="Se usa para calcular caducidad del lote desde la fecha de producción.")
