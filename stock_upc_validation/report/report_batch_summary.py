from collections import defaultdict

from odoo import api, models


class ReportStockUpcBatchSummary(models.AbstractModel):
    _name = 'report.stock_upc_validation.report_batch_summary'
    _description = 'Resumen de piezas por Batch Picking'

    @api.model
    def _get_report_values(self, docids, data=None):
        batches = self.env['stock.picking.batch'].browse(docids)
        lines_by_batch = {}
        for batch in batches:
            grouped = defaultdict(lambda: {
                'product': self.env['product.product'],
                'demand_qty': 0.0,
                'reserved_qty': 0.0,
                'picking_count': 0,
                'pickings': set(),
            })
            moves = batch.picking_ids.mapped('move_ids').filtered(
                lambda m: m.state not in ('cancel', 'done') and m.product_id
            )
            for move in moves:
                key = move.product_id.id
                grouped[key]['product'] = move.product_id
                grouped[key]['demand_qty'] += move.product_uom_qty or 0.0
                grouped[key]['reserved_qty'] += move.quantity or 0.0
                if move.picking_id:
                    grouped[key]['pickings'].add(move.picking_id.id)

            lines = []
            for vals in grouped.values():
                vals['picking_count'] = len(vals['pickings'])
                vals.pop('pickings', None)
                lines.append(vals)
            lines.sort(key=lambda l: ((l['product'].default_code or ''), l['product'].display_name or ''))
            lines_by_batch[batch.id] = lines

        return {
            'doc_ids': docids,
            'doc_model': 'stock.picking.batch',
            'docs': batches,
            'lines_by_batch': lines_by_batch,
        }
