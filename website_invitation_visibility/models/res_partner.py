
# -*- coding: utf-8 -*-
from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_wholesale_access = fields.Boolean(
        string='Acceso Mayoristas',
        help='Si está activo, este contacto puede acceder a páginas marcadas como "Por invitación".'
    )
