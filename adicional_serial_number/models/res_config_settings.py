# -*- coding: utf-8 -*-
from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    adicional_sn_version = fields.Char(
        string="Versión instalada (Adicional Serial Number)",
        compute="_compute_adicional_sn_version",
        readonly=True,
    )

    def _compute_adicional_sn_version(self):
        ICP = self.env["ir.config_parameter"].sudo()
        version = ICP.get_param("adicional_serial_number.version", default="desconocida")
        for rec in self:
            rec.adicional_sn_version = version
