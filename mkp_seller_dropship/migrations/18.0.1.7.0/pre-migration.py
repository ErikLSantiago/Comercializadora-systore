# -*- coding: utf-8 -*-
import logging


_logger = logging.getLogger(__name__)


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = %s
           AND column_name = %s
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    """Move useful legacy values, then remove fields that conflict with Doto."""
    if _column_exists(cr, "res_partner", "mkp_manage_as_seller"):
        if _column_exists(cr, "res_partner", "is_seller_managed"):
            cr.execute(
                """
                UPDATE res_partner
                   SET is_seller_managed = TRUE
                 WHERE COALESCE(mkp_manage_as_seller, FALSE) = TRUE
                """
            )
        cr.execute("ALTER TABLE res_partner DROP COLUMN mkp_manage_as_seller")

    if _column_exists(cr, "sale_order_line", "mkp_product_cost"):
        if _column_exists(cr, "sale_order_line", "x_seller_cost"):
            cr.execute(
                """
                UPDATE sale_order_line
                   SET x_seller_cost = mkp_product_cost
                 WHERE COALESCE(x_seller_cost, 0) = 0
                   AND COALESCE(mkp_product_cost, 0) != 0
                """
            )
        cr.execute("ALTER TABLE sale_order_line DROP COLUMN mkp_product_cost")

    if _column_exists(cr, "sale_order", "seller_id"):
        if _column_exists(cr, "sale_order", "x_studio_dropshipping_seller_id"):
            cr.execute(
                """
                UPDATE sale_order
                   SET x_studio_dropshipping_seller_id = seller_id
                 WHERE x_studio_dropshipping_seller_id IS NULL
                   AND seller_id IS NOT NULL
                """
            )
        cr.execute("ALTER TABLE sale_order DROP COLUMN seller_id")

    if _column_exists(cr, "stock_seller", "seller_id") and _column_exists(
        cr, "stock_seller", "partner_id"
    ):
        cr.execute(
            """
            UPDATE stock_seller
               SET partner_id = seller_id
             WHERE partner_id IS NULL
               AND seller_id IS NOT NULL
            """
        )
    if _column_exists(cr, "stock_seller", "product_id") and _column_exists(
        cr, "stock_seller", "producto_id"
    ):
        cr.execute(
            """
            UPDATE stock_seller
               SET producto_id = product_id
             WHERE producto_id IS NULL
               AND product_id IS NOT NULL
            """
        )

    cr.execute(
        "ALTER TABLE IF EXISTS stock_seller "
        "DROP CONSTRAINT IF EXISTS stock_seller_seller_product_company_uniq"
    )
    for column in ("seller_id", "product_id"):
        if _column_exists(cr, "stock_seller", column):
            cr.execute(
                'ALTER TABLE stock_seller ALTER COLUMN "%s" DROP NOT NULL' % column
            )

    _logger.info(
        "Marketplace Seller Dropship 18.0.1.7.0: legacy seller fields migrated "
        "and conflicting stock.seller constraint removed."
    )
