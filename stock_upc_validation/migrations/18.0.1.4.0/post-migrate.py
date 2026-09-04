from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env['res.company'].search([])
    Warehouse = env['stock.warehouse']
    for company in companies:
        if not company.systore_upc_validation_warehouse_ids:
            warehouses = Warehouse.search([('company_id', '=', company.id)])
            if warehouses:
                company.systore_upc_validation_warehouse_ids = [(6, 0, warehouses.ids)]
