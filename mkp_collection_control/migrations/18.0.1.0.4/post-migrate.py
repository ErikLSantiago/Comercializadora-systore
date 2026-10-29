"""Initialize revision metadata and active-history flags."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE mkp_collection_payment
           SET revision_key = COALESCE(revision_key, 'LEGACY-' || id::text),
               revision_no = COALESCE(revision_no, 1),
               payment_reference = COALESCE(NULLIF(payment_reference, ''), 'LEGACY-' || id::text),
               amount = CASE WHEN amount < 0 THEN -amount ELSE amount END,
               payment_status = CASE
                   WHEN payment_status = 'released' THEN 'paid'
                   WHEN payment_status = 'penalized' THEN 'cancelled'
                   ELSE payment_status
               END,
               is_active_revision = COALESCE(is_active_revision, TRUE)
        """
    )
    cr.execute("UPDATE mkp_collection_event SET is_active_revision = FALSE")
    cr.execute(
        """
        UPDATE mkp_collection_event AS event
           SET is_active_revision = TRUE
          FROM (
              SELECT DISTINCT ON (order_id) id
                FROM mkp_collection_event
               ORDER BY order_id, event_time DESC, id DESC
          ) AS latest
         WHERE event.id = latest.id
        """
    )
    cr.execute(
        """
        UPDATE mkp_collection_event
           SET history_status = CASE WHEN is_active_revision THEN 'active' ELSE 'historical' END
        """
    )
