from collections import OrderedDict

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class ReportMkpWholesaleStatement(models.AbstractModel):
    _name = 'report.mkp_collection_control.report_wholesale_statement'
    _description = 'Estado de cuenta de clientes Mayoreo'

    @api.model
    def _get_report_values(self, docids, data=None):
        if not self.env.user.has_group(
                'mkp_collection_control.group_mkp_collection_operator'):
            raise AccessError(_(
                'Se requiere el permiso Operador de Cobranza MKP.'
            ))
        orders = self.env['sale.order'].browse(docids).exists()
        if not orders:
            raise UserError(_('Seleccione al menos un pedido de Mayoreo.'))
        invalid_orders = orders.filtered(
            lambda order: order.mkp_collection_type != 'wholesale'
        )
        if invalid_orders:
            raise UserError(_(
                'El PDF solo admite pedidos de Mayoreo. Retire de la selección: %s'
            ) % ', '.join(invalid_orders.mapped('name')))

        grouped = OrderedDict()
        sorted_orders = orders.sorted(key=lambda order: (
            (order.partner_invoice_id or order.partner_id).display_name or '',
            order.currency_id.name or '',
            order.name or '',
        ))
        for order in sorted_orders:
            partner = order.partner_invoice_id or order.partner_id
            key = (partner.id, order.currency_id.id)
            if key not in grouped:
                grouped[key] = {
                    'partner': partner,
                    'currency': order.currency_id,
                    'orders': self.env['sale.order'],
                    'net_amount': 0.0,
                    'paid_amount': 0.0,
                    'amount_due': 0.0,
                }
            group = grouped[key]
            group['orders'] |= order
            group['net_amount'] += order.mkp_wholesale_net_expected
            group['paid_amount'] += order.mkp_wholesale_paid
            group['amount_due'] += order.mkp_wholesale_amount_to_collect

        payment_labels = dict(
            self.env['mkp.wholesale.payment']._fields[
                'payment_status'
            ]._description_selection(self.env)
        )
        generated_at = fields.Datetime.context_timestamp(
            self, fields.Datetime.now()
        )
        return {
            'doc_ids': orders.ids,
            'doc_model': 'sale.order',
            'docs': orders,
            'customer_groups': list(grouped.values()),
            'payment_labels': payment_labels,
            'generated_at_text': generated_at.strftime('%d/%m/%Y %H:%M'),
        }
