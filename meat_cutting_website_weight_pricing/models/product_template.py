# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ProductTemplate(models.Model):
    _inherit = "product.template"

    # Peso aproximado para mostrar en el sitio (manual por ahora)
    x_web_avg_weight = fields.Float(string="Peso aproximado (web)", help="Peso aproximado por pieza para mostrar en el sitio web.")
