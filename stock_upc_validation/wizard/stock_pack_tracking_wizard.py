from odoo import _, fields, models
from odoo.exceptions import UserError


class StockPackTrackingWizard(models.TransientModel):
    _name = 'stock.pack.tracking.wizard'
    _description = 'Capturar guía en empaque'

    picking_id = fields.Many2one('stock.picking', string='Traslado de empaque', required=True, readonly=True)
    tracking_ref = fields.Char(string='Número de guía')
    skip_tracking_ref = fields.Boolean(string='No asignar número de guía')

    def action_confirm(self):
        self.ensure_one()
        tracking = (self.tracking_ref or '').strip()
        if not tracking and not self.skip_tracking_ref:
            raise UserError(_('Debe capturar el número de guía.'))

        picking = self.picking_id.sudo()
        if self.skip_tracking_ref:
            picking.message_post(body=_(
                '<b>Número de guía omitido</b><br/>'
                'El usuario <b>%s</b> validó la operación sin asignar número de guía.'
            ) % self.env.user.display_name)
        else:
            picking.write({'carrier_tracking_ref': tracking})
        return picking.with_context(systore_skip_pack_tracking_wizard=True).button_validate()
