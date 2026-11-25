def migrate(cr, version):
    """Allow signed wholesale events and classify existing rows as payments."""
    cr.execute("""
        ALTER TABLE mkp_wholesale_payment
        DROP CONSTRAINT IF EXISTS mkp_wholesale_payment_positive_wholesale_payment_amount
    """)
    cr.execute("""
        ALTER TABLE mkp_wholesale_payment
        DROP CONSTRAINT IF EXISTS positive_wholesale_payment_amount
    """)
    cr.execute("""
        UPDATE mkp_wholesale_payment
           SET operation_type = 'payment'
         WHERE operation_type IS NULL
    """)
