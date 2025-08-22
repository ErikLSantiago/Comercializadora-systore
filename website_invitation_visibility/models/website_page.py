
# -*- coding: utf-8 -*-
from odoo import models, fields

class IrUiView(models.Model):
    _inherit = "ir.ui.view"

    visibility = fields.Selection(
        selection_add=[('invitation', 'Por invitación')],
        ondelete={'invitation': 'set default'},
        help="Por invitación: solo usuarios autenticados con 'Acceso Mayoristas' podrán ver esta página."
    )

    def _is_visible(self, website=False, **kwargs):
        # First let core compute visibility for known modes
        res = super()._is_visible(website=website, **kwargs)
        # If this view uses our custom mode, override the result
        for view in self:
            if getattr(view, 'visibility', None) == 'invitation':
                user = view.env.user
                if user._is_public():
                    res = False
                else:
                    # allow only if partner has wholesale access
                    res = bool(user.partner_id.sudo().is_wholesale_access)
        return res
