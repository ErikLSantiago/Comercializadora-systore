def migrate(cr, version):
    """Give existing snapshots safe values until their selected month is refreshed."""
    cr.execute(
        """
        UPDATE systore_supply_purchase_line
           SET net_received_qty = received_qty,
               movement_status = CASE
                   WHEN received_qty > 0 THEN 'received'
                   ELSE 'pending'
               END
         WHERE movement_status IS NULL
        """
    )
