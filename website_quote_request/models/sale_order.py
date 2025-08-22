# -*- coding: utf-8 -*-
from odoo import models, fields

class SaleOrder(models.Model):
    _inherit = "sale.order"

    wqr_is_request = fields.Boolean(string="Solicitud de cotización (Website)", default=False, help="Marcador para solicitudes generadas desde /quote.")
    wqr_submitted = fields.Boolean(string="Enviada desde website", default=False)
