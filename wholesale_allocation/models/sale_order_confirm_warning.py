from odoo import fields, models, _


class SaleOrderConfirmWarning(models.TransientModel):
    _name = 'sale.order.confirm.warning'
    _description = 'Sale Order Confirmation Warning'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        required=True,
        readonly=True,
    )
    message = fields.Text(
        string='Message',
        readonly=True,
        default=lambda self: _(
            'No ha vinculado una Orden de Compra asociada a esta venta. '
            'El sistema tomará cualquier lote y no habrá trazabilidad de costos '
            '¿Esta seguro que desea continuar?'
        ),
    )

    def action_continue_confirm(self):
        self.ensure_one()
        return self.sale_order_id.with_context(skip_wholesale_po_warning=True).action_confirm()

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}
