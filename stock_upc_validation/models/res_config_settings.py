from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    systore_upc_receipt_warehouse_ids = fields.Many2many(
        related='company_id.systore_upc_receipt_warehouse_ids',
        readonly=False,
        string='Almacenes con UPC/EAN en recepción',
    )
    systore_upc_validation_warehouse_ids = fields.Many2many(
        related='company_id.systore_upc_validation_warehouse_ids',
        readonly=False,
        string='Almacenes con validación UPC/NS/IMEI en salida',
    )

    systore_exclude_partial_pickings_from_batch = fields.Boolean(
        related='company_id.systore_exclude_partial_pickings_from_batch',
        readonly=False,
        string='Excluir órdenes parciales de Batch Picking',
    )
