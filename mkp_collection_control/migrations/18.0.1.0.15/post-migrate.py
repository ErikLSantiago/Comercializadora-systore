def migrate(cr, version):
    """Initialize payments and recompute the remaining balance."""
    cr.execute("""
        UPDATE mkp_collection_line_history
           SET paid_amount = COALESCE(paid_amount, 0),
               amount_to_collect = COALESCE(adjusted_total, 0)
                                   - COALESCE(paid_amount, 0)
    """)
