def migrate(cr, version):
    """Preserve the original author and timestamp of existing payment details."""
    cr.execute("""
        UPDATE mkp_collection_line_payment_detail
           SET registered_by_id = COALESCE(registered_by_id, create_uid),
               registered_at = COALESCE(registered_at, create_date)
    """)
