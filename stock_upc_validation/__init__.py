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

    # Por compatibilidad, si la compañía aún no tiene almacenes configurados,
    # se activan todos sus almacenes para recepción y salida. Después el usuario
    # puede segmentar y dejar fuera almacenes externos/full.
    companies = env['res.company'].search([])
    for company in companies:
        warehouses = env['stock.warehouse'].search([('company_id', '=', company.id)])
        if warehouses and not company.systore_upc_receipt_warehouse_ids:
            company.systore_upc_receipt_warehouse_ids = [(6, 0, warehouses.ids)]
        if warehouses and not company.systore_upc_validation_warehouse_ids:
            company.systore_upc_validation_warehouse_ids = [(6, 0, warehouses.ids)]


def post_init_hook(env):
    _activate_defaults(env)
