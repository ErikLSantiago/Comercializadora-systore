from odoo import _, fields, models
from odoo.exceptions import UserError


class StockPackTrackingWizard(models.TransientModel):
    _name = 'stock.pack.tracking.wizard'
    _description = 'Capturar guía en empaque'

    picking_id = fields.Many2one('stock.picking', string='Traslado de empaque', required=True, readonly=True)
    tracking_ref = fields.Char(string='Número de guía')

    def action_confirm(self):
        self.ensure_one()
        tracking = (self.tracking_ref or '').strip()
        if not tracking:
            raise UserError(_('Debe capturar el número de guía.'))

        picking = self.picking_id.sudo()
        picking.write({'carrier_tracking_ref': tracking})
        return picking.with_context(systore_skip_pack_tracking_wizard=True).button_validate()
