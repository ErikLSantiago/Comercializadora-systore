from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    warehouses = env["stock.warehouse"].with_context(active_test=False).search([])
    for warehouse in warehouses:
        code = (warehouse.code or "").strip().upper()
        name = (warehouse.name or "").strip().upper()
        if code.startswith(("MXMAY", "SDMAY")) or name in (
            "MX: MAYOREO", "SAN DIEGO: MAYOREO",
        ):
            warehouse.systore_supply_management = "wholesale"
        elif warehouse.systore_supply_management not in (
            "wholesale", "retail", "excluded",
        ):
            warehouse.systore_supply_management = "retail"

    access_group = env.ref(
        "systore_purchase_supply_dashboard.group_supply_dashboard_user",
        raise_if_not_found=False,
    )
    purchase_group = env.ref("purchase.group_purchase_user", raise_if_not_found=False)
    if access_group and purchase_group:
        access_group.write({"users": [(6, 0, purchase_group.users.ids)]})
