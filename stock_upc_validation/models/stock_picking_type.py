from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    systore_require_upc_on_receipt = fields.Boolean(
        string='Exigir UPC/EAN en recepción',
        help='Al validar una recepción, solicita registrar/validar UPC/EAN por producto recibido.',
    )
    systore_auto_lot_from_origin = fields.Boolean(
        string='Lote automático desde documento origen',
        help='En recepciones, asigna automáticamente como lote el documento origen, normalmente la orden de compra.',
    )
    systore_require_upc_on_picking = fields.Boolean(
        string='Exigir validación UPC/EAN en recolección',
        help='Al validar este tipo de traslado, solicita escanear UPC/EAN por producto antes de permitir avanzar.',
    )
    systore_upc_validation_per_product = fields.Integer(
        string='Escaneos UPC por producto',
        default=1,
        help='Cantidad mínima de escaneos solicitados por cada producto en la validación de recolección. Para fase 2 normalmente se usa 1.',
    )
    systore_require_tracking_on_pack = fields.Boolean(
        string='Exigir guía en empaque',
        help='Al validar este tipo de traslado, obliga capturar la referencia de rastreo y la propaga al traslado de salida encadenado.',
    )
