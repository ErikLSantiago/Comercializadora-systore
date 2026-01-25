from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # Activar precios por peso basados en serial reservado
    x_use_weight_sale_price = fields.Boolean(
        string="Usar precio por peso (reserva)",
        help="Si está activo, el precio de venta se recalcula con base en el peso (kg) guardado en los seriales reservados."
    )

    # Precio por unidad de peso (por ejemplo: 200 por KG)
    x_price_per_weight = fields.Float(
        string="Precio en peso",
        digits="Product Price",
        help="Precio por unidad de peso (según la unidad seleccionada). Ej: 200 por KG."
    )

    x_price_weight_uom_id = fields.Many2one(
        "uom.uom",
        string="Unidad precio por peso",
        help="Unidad de medida para el precio en peso (ej. KG o g)."
    )
