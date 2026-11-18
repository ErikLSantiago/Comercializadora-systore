from odoo import SUPERUSER_ID, api, fields


def migrate(cr, version):
    """Convert previous aggregate paid amounts into one payment detail."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    histories = env['mkp.collection.line.history'].search([
        ('paid_amount', '>', 0),
    ])
    detail_model = env['mkp.collection.line.payment.detail'].sudo()
    for history in histories:
        if history.payment_detail_ids:
            continue
        payment_date = history.payment_date
        if not payment_date and history.changed_at:
            payment_date = fields.Date.to_date(history.changed_at)
        detail_model.create({
            'history_id': history.id,
            'payment_date': payment_date or fields.Date.context_today(history),
            'amount': history.paid_amount,
            'payment_reference': (
                history.payment_reference or 'Saldo migrado de la versión anterior'
            ),
        })
