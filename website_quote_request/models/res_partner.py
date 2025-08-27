
from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    wqr_quote_access = fields.Boolean(
        string='Acceso a Solicitar Cotización (/quote)',
        help='Si está activo, este contacto puede acceder al catálogo de solicitudes (/quote).',
        default=False,
    )
