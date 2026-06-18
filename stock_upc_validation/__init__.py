from . import models
from . import wizard


def _activate_defaults(env):
    incoming_types = env['stock.picking.type'].search([('code', '=', 'incoming')])
    incoming_types.write({
        'systore_require_upc_on_receipt': True,
        'systore_auto_lot_from_origin': True,
    })
    pick_types = env['stock.picking.type'].search([
        ('code', '=', 'internal'),
        '|',
        ('name', 'ilike', 'pick'),
        ('name', 'ilike', 'recole'),
    ])
    pick_types.write({
        'systore_require_upc_on_picking': True,
        'systore_upc_validation_per_product': 1,
    })
    pack_types = env['stock.picking.type'].search([
        ('code', '=', 'internal'),
        '|', '|', '|',
        ('name', 'ilike', 'pack'),
        ('name', 'ilike', 'empaque'),
        ('name', 'ilike', 'empaquet'),
        ('name', 'ilike', 'zona de empaque'),
    ])
    pack_types.write({'systore_require_tracking_on_pack': True})


def post_init_hook(env):
    _activate_defaults(env)
