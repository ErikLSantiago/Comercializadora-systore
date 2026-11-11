def migrate(cr, version):
    """Initialize the return status on revisions created by earlier versions."""
    cr.execute("""
        UPDATE mkp_collection_line_history
           SET return_status = COALESCE(return_status, 'sale')
    """)
