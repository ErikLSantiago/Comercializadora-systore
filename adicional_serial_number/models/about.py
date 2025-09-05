# -*- coding: utf-8 -*-
from odoo import models, fields

class AdicionalSNAbout(models.TransientModel):
    _name = "adicional.sn.about"
    _description = "Acerca de Adicional Serial Number"

    version = fields.Char(string="Versión instalada", compute="_compute_version")

    def _compute_version(self):
        ICP = self.env['ir.config_parameter'].sudo()
        ver = ICP.get_param('adicional_serial_number.version', default='desconocida')
        for rec in self:
            rec.version = ver
