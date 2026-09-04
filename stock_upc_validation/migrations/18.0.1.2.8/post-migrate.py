from odoo import api, SUPERUSER_ID


def _safe_write_if_fields(env, records, vals):
    vals = {k: v for k, v in vals.items() if k in records._fields}
    if records and vals:
        records.write(vals)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    PickingType = env['stock.picking.type']

    pick_types = PickingType.search([
        ('code', '=', 'internal'),
        '|',
        ('name', 'ilike', 'pick'),
        ('name', 'ilike', 'recole'),
    ])
    _safe_write_if_fields(env, pick_types, {
        'systore_require_upc_on_picking': True,
        'systore_upc_validation_per_product': 1,
    })

    pack_types = PickingType.search([
        ('code', '=', 'internal'),
        '|', '|', '|',
        ('name', 'ilike', 'pack'),
        ('name', 'ilike', 'empaque'),
        ('name', 'ilike', 'empaquet'),
        ('name', 'ilike', 'zona de empaque'),
    ])
    _safe_write_if_fields(env, pack_types, {
        'systore_require_tracking_on_pack': True,
    })
