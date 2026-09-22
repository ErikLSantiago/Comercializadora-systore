from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Release legacy manual Pending/Partial overrides back to automatic mode."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    orders = env["purchase.order"].search([
        ("systore_payment_status_manual", "in", ["pending", "partial"]),
    ])
    orders.write({"systore_payment_status_manual": "automatic"})
