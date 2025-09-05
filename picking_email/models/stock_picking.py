# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class StockPicking(models.Model):
    _inherit = "stock.picking"

    def action_send_email(self):
        self.ensure_one()
        template = self.env['mail.template']._get_default_template_for_model('stock.picking')

        compose_form = self.env.ref('mail.email_compose_message_wizard_form')
        partners = []
        if self.partner_id:
            partners = [self.partner_id.id]

        ctx = {
            'default_model': 'stock.picking',
            'default_res_ids': [self.id],
            'default_use_template': bool(template),
            'default_template_id': template.id if template else False,
            'default_composition_mode': 'comment',
            'default_partner_ids': partners,
            'force_email': True,
        }

        return {
            'name': _('Enviar por correo'),
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'views': [(compose_form.id, 'form')],
            'target': 'new',
            'context': ctx,
        }