# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class MailTemplate(models.Model):
    _inherit = "mail.template"

    is_favorite = fields.Boolean(
        string="Favorita (para este modelo)",
        help="Si se activa, esta plantilla será la predeterminada al enviar correos "
             "desde el modelo indicado. Solo puede existir una favorita por modelo "
             "y compañía.",
    )

    @api.constrains('is_favorite', 'model_id', 'company_id')
    def _check_unique_favorite_per_model_company(self):
        for rec in self:
            if rec.is_favorite and rec.model_id:
                domain = [
                    ('id', '!=', rec.id),
                    ('is_favorite', '=', True),
                    ('model_id', '=', rec.model_id.id),
                ]
                # Mismo comportamiento que otras plantillas: permitir plantillas
                # sin compañía (global) o de la misma compañía
                if rec.company_id:
                    domain += ['|', ('company_id', '=', rec.company_id.id), ('company_id', '=', False)]
                count_fav = self.search_count(domain)
                if count_fav:
                    raise ValidationError(_("Solo puede existir una plantilla favorita por modelo y compañía."))

    @api.model
    def _get_default_template_for_model(self, model, company_id=None):
        """Obtiene la plantilla favorita para un modelo (y compañía),
        o en su defecto, cualquier plantilla del modelo.
        """
        domain = [('model_id.model', '=', model)]
        if company_id:
            domain += ['|', ('company_id', '=', company_id), ('company_id', '=', False)]

        favorite = self.search(domain + [('is_favorite', '=', True)], limit=1)
        if favorite:
            return favorite

        # Fallback a cualquier plantilla del modelo
        return self.search(domain, limit=1)