
from odoo import models, fields

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    wqr_total_pieces = fields.Integer(
        string='Piezas solicitadas',
        readonly=True,
        copy=False,
        help='Total de piezas solicitadas desde el sitio (suma de cantidades de líneas al crear la cotización).',
    )
