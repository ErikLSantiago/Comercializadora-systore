from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    # ---------------------------------------------------------------------
    # Legacy fields kept only so databases that installed 18.0.1.0.0 can be
    # upgraded safely. They are no longer used by the engine; configuration
    # now lives on stock.rule with action = 'surplus'.
    # ---------------------------------------------------------------------
    surplus_transfer_enabled = fields.Boolean(
        string='Transferir excedente automáticamente (obsoleto)',
    )
    surplus_source_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación origen del excedente (obsoleto)',
        check_company=True,
    )
    surplus_destination_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacén destino (obsoleto)',
        check_company=True,
    )
    surplus_destination_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación destino (obsoleto)',
        check_company=True,
    )
    surplus_picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Tipo de operación destino (obsoleto)',
        check_company=True,
    )
