"""Map legacy event concepts to the four visible payment states."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE mkp_collection_event
           SET payment_state = CASE
               WHEN event_type = 'refund' THEN 'refund'
               WHEN event_type IN ('coupon', 'killer', 'commission', 'tax', 'shipping', 'other')
                   THEN 'recalculated'
               WHEN event_type IN ('hold', 'unlock', 'release', 'release_direct', 'payment')
                   THEN 'confirmed'
               ELSE 'draft'
           END,
               is_reversal_entry = (event_type = 'reversal')
        """
    )
    cr.execute(
        """
        UPDATE mkp_collection_order AS collection
           SET payment_state = COALESCE(
               (
                   SELECT event.payment_state
                     FROM mkp_collection_event AS event
                    WHERE event.order_id = collection.id
                      AND NOT event.is_reversal_entry
                    ORDER BY event.event_time DESC, event.id DESC
                    LIMIT 1
               ),
               'draft'
           )
        """
    )
