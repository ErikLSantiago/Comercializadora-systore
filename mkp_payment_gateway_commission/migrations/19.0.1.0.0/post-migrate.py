# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Preserve the gateway selected by the former partner-based field."""
    cr.execute(
        """
        UPDATE sale_order AS sale
           SET mkp_payment_gateway_config_id = config.id
          FROM mkp_payment_gateway_config AS config
         WHERE sale.mkp_payment_gateway_config_id IS NULL
           AND sale.mkp_payment_gateway_partner_id = config.partner_id
           AND sale.company_id = config.company_id
           AND config.active
        """
    )
