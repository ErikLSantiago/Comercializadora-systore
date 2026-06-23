from odoo import _, models


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    def _systore_needs_upc_batch_wizard(self):
        self.ensure_one()
        if self.env.context.get('systore_skip_upc_batch_wizard'):
            return False
        pickings = self.picking_ids.filtered(lambda p: p._systore_needs_upc_picking_wizard())
        return bool(pickings)

    def _systore_open_upc_batch_wizard(self):
        self.ensure_one()
        wizard = self.env['stock.picking.upc.wizard'].create_from_batch(self)
        return {
            'name': _('Validar UPC/EAN de batch'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking.upc.wizard',
            'view_mode': 'form',
            'target': 'new',
            'res_id': wizard.id,
        }

    def action_done(self):
        batches = self.filtered(lambda b: b._systore_needs_upc_batch_wizard())
        if batches:
            return batches[0]._systore_open_upc_batch_wizard()
        return super().action_done()

    def button_validate(self):
        batches = self.filtered(lambda b: b._systore_needs_upc_batch_wizard())
        if batches:
            return batches[0]._systore_open_upc_batch_wizard()
        parent = getattr(super(), 'button_validate', None)
        if parent:
            return parent()
        return self.action_done()
