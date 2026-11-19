def migrate(cr, version):
    """Extend unit commissions by quantity and refresh stored balances."""
    cr.execute("""
        WITH calculated AS (
            SELECT id,
                   ABS(COALESCE(quantity, 0))::numeric AS pieces,
                   ROUND(
                       COALESCE(amount, 0)
                       - COALESCE(coupon_amount, 0)
                       + COALESCE(killer_amount, 0),
                       2
                   ) AS new_subtotal
              FROM mkp_collection_line_history
        ), totals AS (
            SELECT history.id,
                   calculated.new_subtotal,
                   ROUND(
                       COALESCE(history.killer_commission, 0)
                       * calculated.pieces,
                       2
                   ) AS new_killer_commission_total,
                   ROUND(
                       COALESCE(history.commission, 0)
                       * calculated.pieces,
                       2
                   ) AS new_commission_total,
                   ROUND(
                       COALESCE(history.other_commission, 0)
                       * calculated.pieces,
                       2
                   ) AS new_other_commission_total
              FROM mkp_collection_line_history AS history
              JOIN calculated ON calculated.id = history.id
        )
        UPDATE mkp_collection_line_history AS history
           SET subtotal = totals.new_subtotal,
               killer_commission_total = totals.new_killer_commission_total,
               commission_total = totals.new_commission_total,
               other_commission_total = totals.new_other_commission_total,
               adjusted_total = ROUND(
                   totals.new_subtotal
                   - totals.new_killer_commission_total
                   - totals.new_commission_total
                   - COALESCE(history.taxes, 0)
                   - COALESCE(history.shipping, 0)
                   - totals.new_other_commission_total,
                   2
               ),
               amount_to_collect = ROUND(
                   totals.new_subtotal
                   - totals.new_killer_commission_total
                   - totals.new_commission_total
                   - COALESCE(history.taxes, 0)
                   - COALESCE(history.shipping, 0)
                   - totals.new_other_commission_total
                   - COALESCE(history.paid_amount, 0),
                   2
               )
          FROM totals
         WHERE totals.id = history.id
    """)
