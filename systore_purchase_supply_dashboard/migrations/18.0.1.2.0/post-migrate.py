def migrate(cr, version):
    """Discard obsolete snapshots; operational and accounting records are untouched."""
    cr.execute("DELETE FROM systore_supply_demand_line")
    cr.execute("DELETE FROM systore_supply_purchase_line")
    cr.execute("DELETE FROM systore_supply_trace_line")
