from odoo import api, fields, models


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
        help='Al validar este tipo de traslado, solicita escanear UPC/EAN por producto antes de permitir avanzar. En almacenes de 2 pasos, Recolectar usa automáticamente el flujo completo de Empaque.',
    )
    systore_upc_validation_per_product = fields.Integer(
        string='Escaneos UPC por producto',
        default=1,
        help='Cantidad mínima de escaneos solicitados por cada producto en la validación de recolección.',
    )
    systore_require_tracking_on_pack = fields.Boolean(
        string='Exigir guía en empaque',
        help='Compatibilidad con configuraciones existentes. El módulo detecta automáticamente el paso equivalente a Empaque según la configuración nativa del almacén.',
    )
    systore_delivery_steps_info = fields.Char(
        string='Pasos de entrega del almacén',
        compute='_compute_systore_delivery_flow_info',
    )
    systore_effective_pack_step = fields.Boolean(
        string='Paso equivalente a Empaque',
        compute='_compute_systore_delivery_flow_info',
    )
    systore_pack_flow_info = fields.Char(
        string='Flujo Systore aplicado',
        compute='_compute_systore_delivery_flow_info',
    )

    @api.depends('warehouse_id', 'warehouse_id.delivery_steps')
    def _compute_systore_delivery_flow_info(self):
        labels = {
            'ship_only': '1 paso',
            'pick_ship': '2 pasos',
            'pick_pack_ship': '3 pasos',
        }
        for picking_type in self:
            warehouse = picking_type.warehouse_id
            steps = getattr(warehouse, 'delivery_steps', False) if warehouse else False
            picking_type.systore_delivery_steps_info = labels.get(steps, 'No aplica')
            is_pack = False
            if warehouse and steps == 'pick_pack_ship':
                is_pack = bool(warehouse.pack_type_id and picking_type == warehouse.pack_type_id)
            elif warehouse and steps == 'pick_ship':
                is_pack = bool(warehouse.pick_type_id and picking_type == warehouse.pick_type_id)
            elif warehouse and steps == 'ship_only':
                is_pack = bool(warehouse.out_type_id and picking_type == warehouse.out_type_id)
            picking_type.systore_effective_pack_step = is_pack
            if is_pack:
                picking_type.systore_pack_flow_info = 'Flujo completo: UPC/EAN + NS/IMEI + guía'
            elif picking_type.systore_require_upc_on_picking:
                picking_type.systore_pack_flow_info = 'Validación UPC/EAN de recolección'
            elif picking_type.systore_require_upc_on_receipt:
                picking_type.systore_pack_flow_info = 'Validación UPC/EAN de recepción'
            else:
                picking_type.systore_pack_flow_info = 'Sin validación Systore automática'
