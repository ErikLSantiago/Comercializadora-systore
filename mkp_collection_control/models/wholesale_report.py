from collections import OrderedDict
from datetime import date

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
        payment_model = self.env['mkp.wholesale.payment']
        payment_labels = dict(
            payment_model._fields[
                'payment_status'
            ]._description_selection(self.env)
        )
        operation_labels = dict(
            payment_model._fields[
                'operation_type'
            ]._description_selection(self.env)
        )
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
                    'statement_lines': [],
                }
            group = grouped[key]
            group['orders'] |= order
            order_date = fields.Datetime.context_timestamp(
                order, order.date_order
            ).date() if order.date_order else False
            group['statement_lines'].append({
                'sort_key': (order_date or date.max, 0, order.id, 0),
                'operation_type': _('Factura'),
                'payment_status': False,
                'document': order.name,
                'customer_reference': order.client_order_ref or '',
                'net_amount': order.amount_total,
                'paid_amount': 0.0,
                'date': order_date,
            })
            if order.mkp_wholesale_general_expense:
                group['statement_lines'].append({
                    'sort_key': (order_date or date.max, 1, order.id, 0),
                    'operation_type': _('Descuento'),
                    'payment_status': _('Aplicado'),
                    'document': (
                        order.mkp_wholesale_expense_note
                        or _('Gasto general de %s') % order.name
                    ),
                    'customer_reference': order.client_order_ref or '',
                    'net_amount': -order.mkp_wholesale_general_expense,
                    'paid_amount': 0.0,
                    'date': order_date,
                })
            for payment in order.mkp_wholesale_payment_ids:
                net_amount = 0.0
                paid_amount = 0.0
                if payment.payment_status == 'paid':
                    if payment.operation_type == 'payment':
                        paid_amount = payment.amount
                    else:
                        net_amount = payment.amount
                elif payment.payment_status == 'refund':
                    if payment.operation_type == 'payment':
                        paid_amount = -payment.amount
                    else:
                        net_amount = -payment.amount
                payment_date = payment.payment_date
                if not payment_date and payment.create_date:
                    payment_date = fields.Datetime.context_timestamp(
                        payment, payment.create_date
                    ).date()
                group['statement_lines'].append({
                    'sort_key': (
                        payment_date or date.max, 2, order.id, payment.id
                    ),
                    'operation_type': operation_labels.get(
                        payment.operation_type, payment.operation_type
                    ),
                    'payment_status': payment_labels.get(
                        payment.payment_status, payment.payment_status
                    ),
                    'document': payment.payment_reference,
                    'customer_reference': order.client_order_ref or '',
                    'net_amount': net_amount,
                    'paid_amount': paid_amount,
                    'date': payment_date,
                })

        for group in grouped.values():
            running_balance = 0.0
            net_amount = 0.0
            paid_amount = 0.0
            lines = sorted(
                group['statement_lines'], key=lambda line: line['sort_key']
            )
            for line in lines:
                net_amount += line['net_amount']
                paid_amount += line['paid_amount']
                running_balance += line['net_amount'] - line['paid_amount']
                line['amount_due'] = running_balance
                line['date_text'] = (
                    line['date'].strftime('%d/%m/%Y') if line['date'] else ''
                )
            group['statement_lines'] = lines
            group['net_amount'] = net_amount
            group['paid_amount'] = paid_amount
            group['amount_due'] = running_balance

        generated_at = fields.Datetime.context_timestamp(
            self, fields.Datetime.now()
        )
        return {
            'doc_ids': orders.ids,
            'doc_model': 'sale.order',
            'docs': orders,
            'customer_groups': list(grouped.values()),
            'generated_at_text': generated_at.strftime('%d/%m/%Y %H:%M'),
        }
