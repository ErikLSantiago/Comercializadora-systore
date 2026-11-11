def migrate(cr, version):
    """Initialize the return quantity on revisions from earlier versions."""
    cr.execute("""
        UPDATE mkp_collection_line_history
           SET return_quantity = COALESCE(return_quantity, 0)
    """)
