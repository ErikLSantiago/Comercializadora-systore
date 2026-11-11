def migrate(cr, version):
    """Initialize new selections and remove coupon commission from line totals."""
    cr.execute("""
        UPDATE mkp_collection_line_history
           SET payment_status = COALESCE(payment_status, 'pending'),
               calculation_type = COALESCE(calculation_type, 'precalculation'),
               subtotal = COALESCE(amount, 0)
                          - COALESCE(coupon_amount, 0)
                          + COALESCE(killer_amount, 0),
               adjusted_total = COALESCE(amount, 0)
                          - COALESCE(coupon_amount, 0)
                          + COALESCE(killer_amount, 0)
                          - COALESCE(killer_commission, 0)
                          - COALESCE(commission, 0)
                          - COALESCE(taxes, 0)
                          - COALESCE(shipping, 0)
                          - COALESCE(other_commission, 0),
               amount_to_collect = COALESCE(amount, 0)
                          - COALESCE(coupon_amount, 0)
                          + COALESCE(killer_amount, 0)
                          - COALESCE(killer_commission, 0)
                          - COALESCE(commission, 0)
                          - COALESCE(taxes, 0)
                          - COALESCE(shipping, 0)
                          - COALESCE(other_commission, 0)
    """)
