from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    systore_upc_receipt_warehouse_ids = fields.Many2many(
        'stock.warehouse',
        'systore_company_upc_receipt_warehouse_rel',
        'company_id',
        'warehouse_id',
        string='Almacenes con UPC/EAN en recepción',
        help='En estos almacenes, las recepciones obligarán capturar UPC/EAN y asignarán el lote desde el documento origen cuando el tipo de operación lo tenga activado.',
    )
    systore_upc_validation_warehouse_ids = fields.Many2many(
        'stock.warehouse',
        'systore_company_upc_validation_warehouse_rel',
        'company_id',
        'warehouse_id',
        string='Almacenes con validación UPC/NS/IMEI en salida',
        help='Solo los traslados de salida/recolección/empaque pertenecientes a estos almacenes ejecutarán el flujo de validación UPC/EAN, NS/IMEI y guía de empaque.',
    )

    systore_exclude_partial_pickings_from_batch = fields.Boolean(
        string='Excluir órdenes parciales de Batch Picking',
        help='Cuando está activo, las recolecciones parcialmente disponibles no se asignan a Batch Picking. Aplica a almacenes configurados para validación UPC/NS/IMEI en salida.',
    )
