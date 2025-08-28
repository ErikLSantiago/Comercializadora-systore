# models/sale_order.py
from odoo import models, api
import requests
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            self._trigger_endpoint(order, 'confirmed')
        return res

    def _trigger_endpoint(self, order, state):
        endpoint_url = 'https://odoo.doto.com.mx/api/v1/vtex/invoice/order'
        headers = {
            'Content-Type': 'application/json',
            'mkp': 'doto'
        }
        data = {
            'order_id': order.id,
            'state': state
        }
        response = requests.post(endpoint_url, json=data, headers=headers)
        if response.status_code != 200:
            _logger.error(
                'Failed to trigger endpoint for sale order %s', order.name)
