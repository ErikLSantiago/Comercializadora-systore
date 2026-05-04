from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    is_manual_external_lot = fields.Boolean(
        string='Manual External Lot',
        compute='_compute_is_manual_external_lot',
        store=True,
        help='Checked when the selected lot does not belong to the associated purchase orders of the sale order.',
    )

    @api.depends('lot_id', 'picking_id.associated_purchase_order_ids', 'move_id.picking_id')
    def _compute_is_manual_external_lot(self):
        for line in self:
            picking = line.picking_id or line.move_id.picking_id
            if not picking or not picking.is_wholesale_allocation or not line.lot_id:
                line.is_manual_external_lot = False
                continue
            allowed_names = set(picking.associated_purchase_order_ids.mapped('name'))
            line.is_manual_external_lot = bool(allowed_names and line.lot_id.name not in allowed_names)
