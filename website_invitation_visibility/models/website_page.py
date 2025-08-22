
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
        res = super()._is_visible(website=website, **kwargs)
        for view in self:
            if getattr(view, 'visibility', None) == 'invitation':
                user = view.env.user.sudo()
                if user._is_public():
                    res = False
                else:
                    p = user.partner_id.sudo()
                    allowed = bool(p and (
                        getattr(p, 'is_wholesale_access', False) or
                        (p.parent_id and getattr(p.parent_id, 'is_wholesale_access', False)) or
                        (p.commercial_partner_id and getattr(p.commercial_partner_id, 'is_wholesale_access', False))
                    ))
                    res = allowed
        return res
