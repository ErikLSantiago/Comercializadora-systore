# -*- coding: utf-8 -*-
from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = "product.template"

    quote_publish = fields.Boolean(string="Publicar para cotización", default=False, help="Muestra este producto en la página de solicitud de cotización.")
    quote_hide_price = fields.Boolean(string="Ocultar precio (cotización web)", default=False, help="Oculta el precio al mostrar el producto en la página de cotización.")
