# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class MailTemplate(models.Model):
    _inherit = "mail.template"

    is_favorite = fields.Boolean(
        string="Favorita (para este modelo)",
        help="Si se activa, esta plantilla será la predeterminada al enviar correos "
             "desde el modelo indicado. Solo puede existir una favorita por modelo.",
    )

    @api.constrains('is_favorite', 'model_id')
    def _check_unique_favorite_per_model(self):
        for rec in self:
            if rec.is_favorite and rec.model_id:
                domain = [
                    ('id', '!=', rec.id),
                    ('is_favorite', '=', True),
                    ('model_id', '=', rec.model_id.id),
                ]
                if self.search_count(domain):
                    raise ValidationError(_("Solo puede existir una plantilla favorita por modelo."))

    @api.model
    def _get_default_template_for_model(self, model):
        """Obtiene la plantilla favorita para un modelo o, en su defecto,
        cualquier plantilla del modelo.
        """
        domain = [('model_id.model', '=', model)]
        favorite = self.search(domain + [('is_favorite', '=', True)], limit=1)
        if favorite:
            return favorite
        return self.search(domain, limit=1)