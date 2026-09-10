# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID

def post_init_hook(env):
    """Best-effort cleanup to avoid UI crashes due to unreadable invoice contacts.

    If some sale orders already have partner_invoice_id set to a contact that the current user's
    record rules cannot read (often due to multi-company restrictions), OWL can crash when rendering.
    Here we normalize obviously invalid cross-company invoice partners by falling back to partner_id.
    """
    # Use a savepoint so we never break installation
    cr = env.cr
    with cr.savepoint():
        # Only handle the most common multi-company pitfall: invoice partner belongs to another company.
        # If partner_invoice has company_id different from sale order company, reset to customer partner_id.
        cr.execute("""
            UPDATE sale_order so
               SET partner_invoice_id = so.partner_id
              FROM res_partner rp
             WHERE so.partner_invoice_id = rp.id
               AND rp.company_id IS NOT NULL
               AND so.company_id IS NOT NULL
               AND rp.company_id <> so.company_id
        """)
