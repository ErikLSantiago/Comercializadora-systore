
from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    quote_publish = fields.Boolean(
        string='Publicar en /quote',
        help='Si está activo, este producto aparece en el catálogo de solicitudes (/quote).',
        default=False,
    )
