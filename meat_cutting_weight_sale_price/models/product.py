from odoo import api, fields, models, _
from odoo.exceptions import UserError

class ProductTemplate(models.Model):
    _inherit = "product.template"

    x_use_weight_sale_price = fields.Boolean(
        string="Usar precio por peso (reserva)",
        help="Si está activo, el precio de venta se recalcula al reservar seriales, usando el peso del lote/serial."
    )
    x_price_per_weight = fields.Float(
        string="Precio en peso",
        help="Precio por unidad de peso (ej. 200 por kg).",
        digits="Product Price",
    )
    x_price_weight_uom_id = fields.Many2one(
        "uom.uom",
        string="Unidad de precio en peso",
        help="Unidad de medida para el precio por peso (normalmente kg).",
        default=lambda self: self.env.ref("uom.product_uom_kgm", raise_if_not_found=False),
    )

    @api.constrains("x_use_weight_sale_price", "x_price_per_weight")
    def _check_price_per_weight(self):
        for p in self:
            if p.x_use_weight_sale_price and p.x_price_per_weight <= 0:
                raise UserError(_("El 'Precio en peso' debe ser mayor a 0 para productos con precio por peso."))
