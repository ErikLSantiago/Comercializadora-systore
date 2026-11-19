def migrate(cr, version):
    """Initialize the collection type on existing orders and revisions."""
    cr.execute("""
        UPDATE sale_order
           SET mkp_collection_type = COALESCE(mkp_collection_type, 'marketplace')
    """)
    cr.execute("""
        UPDATE mkp_collection_order
           SET collection_type = COALESCE(collection_type, 'marketplace')
    """)
    cr.execute("""
        UPDATE sale_order AS sale
           SET mkp_collection_type = collection.collection_type
          FROM mkp_collection_order AS collection
         WHERE collection.sale_order_id = sale.id
    """)
    cr.execute("""
        UPDATE mkp_collection_line_history AS history
           SET collection_type = collection.collection_type
          FROM mkp_collection_order AS collection
         WHERE history.order_id = collection.id
    """)
