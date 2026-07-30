def post_init_hook(env):
    """Grant historical salespeople access to restricted order contacts."""
    orders = env["sale.order"].sudo().search([
        ("user_id", "!=", False),
        ("partner_id", "!=", False),
    ])
    orders._sync_contact_privacy_users()

