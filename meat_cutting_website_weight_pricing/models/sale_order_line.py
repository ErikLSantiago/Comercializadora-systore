from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    mc_web_lot_display = fields.Char(
        string='Lote asignado (Web)',
        compute='_compute_mc_web_lot_display',
        help='Lote(s) que el sistema asignó para esta línea durante el checkout web.',
    )

    @api.depends(
        'order_id',
        'order_id.mc_web_reservation_ids',
        'order_id.mc_web_reservation_ids.order_line_id',
        'order_id.mc_web_reservation_ids.lot_id',
    )
    def _compute_mc_web_lot_display(self):
        Reservation = self.env['mc.web.reservation'].sudo()
        line_ids = self.ids
        if not line_ids:
            for line in self:
                line.mc_web_lot_display = False
            return

        reservations = Reservation.search([
            ('order_line_id', 'in', line_ids),
            ])

        lots_by_line = {}
        for r in reservations:
            if r.order_line_id and r.lot_id:
                lots_by_line.setdefault(r.order_line_id.id, []).append(r.lot_id.name)

        for line in self:
            names = lots_by_line.get(line.id) or []
            # If qty > 1, show multiple lots separated by comma.
            line.mc_web_lot_display = ', '.join(names) if names else False
