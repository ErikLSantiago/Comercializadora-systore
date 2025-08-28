# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.
from odoo import models


class Picking(models.Model):
    _inherit = 'stock.picking'

    def action_send_email(self):
        """ Open a window to compose an email, with the edi invoice template
            message loaded by default
        """
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        try:
            template_id = ir_model_data._xmlid_to_res_id(
                'sh_picking_send_email.email_template_edi_stock', raise_if_not_found=False)
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data._xmlid_to_res_id(
                'mail.email_compose_message_wizard_form', raise_if_not_found=False)
        except ValueError:
            compose_form_id = False
        ctx = {
            'default_model': 'stock.picking',
            'default_res_id': self.ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'force_email': True
        }
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }
