from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    pickings = env['stock.picking'].search([('state', 'not in', ('done', 'cancel'))])
    if pickings:
        pickings._compute_systore_batch_readiness_state()
