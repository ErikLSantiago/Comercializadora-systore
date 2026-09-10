from odoo import _, models
from odoo.exceptions import UserError


class StockPickingToBatch(models.TransientModel):
    _inherit = 'stock.picking.to.batch'

    def attach_pickings(self):
        """Exclude partial pickings before Odoo writes batch_id.

        Previous versions tried to intercept stock.picking.write({'batch_id': ...}).
        That is too late and can be bypassed depending on the wizard/context. Filtering
        directly in stock.picking.to.batch is more reliable because this is the native
        path used by Batch Picking > Add to batch / Create batch.
        """
        for wizard in self:
            pickings = wizard._systore_get_candidate_pickings()
            if not pickings:
                continue

            to_skip = pickings.filtered(lambda p: p._systore_should_exclude_from_batch())
            if not to_skip:
                continue

            eligible = pickings - to_skip
            wizard._systore_set_candidate_pickings(eligible)

            if wizard._fields.get('batch_id') and wizard.batch_id and hasattr(wizard.batch_id, 'message_post'):
                wizard.batch_id.message_post(body=wizard._systore_partial_batch_message(to_skip))

            if not eligible:
                raise UserError(_(
                    'No se creó/actualizó el lote porque todas las recolecciones seleccionadas tienen piezas en espera o cantidades parciales.\n\n%s'
                ) % '\n'.join(to_skip.mapped('name')))

        return super().attach_pickings()

    def _systore_get_candidate_pickings(self):
        self.ensure_one()
        if 'picking_ids' in self._fields:
            return self.picking_ids
        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids') or []
        if active_model == 'stock.picking' and active_ids:
            return self.env['stock.picking'].browse(active_ids).exists()
        return self.env['stock.picking']

    def _systore_set_candidate_pickings(self, pickings):
        self.ensure_one()
        if 'picking_ids' in self._fields:
            self.picking_ids = [(6, 0, pickings.ids)]

    def _systore_partial_batch_message(self, pickings):
        self.ensure_one()
        return _(
            'Se excluyeron las siguientes recolecciones del Batch Picking porque tienen piezas en espera o cantidades parciales: %s'
        ) % ', '.join(pickings.mapped('name'))
