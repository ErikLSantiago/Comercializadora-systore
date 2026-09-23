from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Recalculate supplier-only balances and synchronize stored snapshots."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    PurchaseOrder = env["purchase.order"].with_context(active_test=False)
    order_ids = PurchaseOrder.search([]).ids

    for start in range(0, len(order_ids), 500):
        orders = PurchaseOrder.browse(order_ids[start:start + 500])
        orders._compute_systore_payment_obligations()
        orders._compute_systore_payment_totals()
        orders._compute_systore_credit_amounts()
        env.flush_all()

    cr.execute(
        """
        UPDATE systore_supply_purchase_line AS line
           SET payment_status = purchase.systore_payment_status,
               amount_payable_mxn = purchase.systore_amount_payable_mxn,
               amount_payable_usd = purchase.systore_merchandise_payable_usd,
               amount_paid_mxn = purchase.systore_amount_paid_mxn,
               amount_paid_usd = purchase.systore_amount_paid_usd,
               amount_pending_mxn = purchase.systore_amount_pending_mxn,
               amount_pending_usd = purchase.systore_amount_pending_usd,
               effective_exchange_rate = purchase.systore_effective_exchange_rate
          FROM purchase_order AS purchase
         WHERE line.purchase_order_id = purchase.id
        """
    )
