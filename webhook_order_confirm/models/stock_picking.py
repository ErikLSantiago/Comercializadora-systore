from odoo import models, api
import requests
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_assign(self):
        res = super(StockPicking, self).action_assign()
        for picking in self:
            if picking.state == 'assigned':
                picking._send_sale_order_to_endpoint('assigned')
        return res

    def button_validate(self):
        res = super(StockPicking, self).button_validate()
        for picking in self:
            if picking.state == 'done':
                picking._send_sale_order_to_endpoint('done')
        return res
    
    def write(self, vals):
        res = super(StockPicking, self).write(vals)
        if 'state' in vals:
            if vals['state'] == 'assigned':
                self._send_sale_order_to_endpoint('assigned')
            elif vals['state'] == 'done':
                self._send_sale_order_to_endpoint('done')
        return res

    def _send_sale_order_to_endpoint(self, state):
        for picking in self:
            if picking.sale_id:
                sale_order_data = {
                    'order_id': picking.sale_id.id,
                    'state': state
                }
                endpoint = "https://odoo.doto.com.mx/api/v1/vtex/invoice/order"
                headers = {'Content-Type': 'application/json', 'mkp': 'doto'}
                try:
                    response = requests.post(endpoint, json=sale_order_data, headers=headers)
                    response.raise_for_status()
                    _logger.info(f"Sale order {picking.sale_id.id} successfully sent to endpoint.")
                except requests.exceptions.RequestException as e:
                    _logger.error(f"Error sending sale order {picking.sale_id.id} to endpoint: {e}")