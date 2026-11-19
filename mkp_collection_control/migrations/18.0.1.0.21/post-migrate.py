from odoo import SUPERUSER_ID, api, fields


def migrate(cr, version):
    """Move the experimental wholesale aggregate into the separate sale tab."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    histories = env['mkp.collection.line.history'].sudo().search([
        ('collection_type', '=', 'wholesale'),
        ('sale_line_id', '=', False),
        ('is_active_revision', '=', True),
    ])
    for history in histories:
        sale = history.sale_order_id
        if not sale or sale.mkp_collection_type != 'wholesale':
            continue
        if not sale.mkp_wholesale_general_expense:
            expense = max(sale.amount_total - history.adjusted_total, 0.0)
            sale.with_context(tracking_disable=True).write({
                'mkp_wholesale_general_expense': expense,
                'mkp_wholesale_expense_note': (
                    'Migrado de la captura general de la versión 18.0.1.0.20'
                ),
            })
        if history.paid_amount > 0 and not sale.mkp_wholesale_payment_ids:
            env['mkp.wholesale.payment'].with_context(
                mkp_skip_wholesale_log=True
            ).create({
                'sale_order_id': sale.id,
                'payment_date': (
                    history.payment_date or fields.Date.context_today(sale)
                ),
                'payment_reference': (
                    history.payment_reference
                    or 'Pago migrado de la versión 18.0.1.0.20'
                ),
                'amount': history.paid_amount,
                'payment_status': 'paid',
                'notes': 'Migrado desde el historial general anterior.',
            })
