from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for company in env['res.company'].search([]):
        warehouses = env['stock.warehouse'].search([('company_id', '=', company.id)])
        if not warehouses:
            continue
        if not company.systore_upc_receipt_warehouse_ids:
            # La mayoría de almacenes deben capturar UPC en entrada: por seguridad
            # se habilitan todos en la nueva configuración y luego se pueden excluir.
            company.systore_upc_receipt_warehouse_ids = [(6, 0, warehouses.ids)]
        if not company.systore_upc_validation_warehouse_ids:
            company.systore_upc_validation_warehouse_ids = [(6, 0, warehouses.ids)]
