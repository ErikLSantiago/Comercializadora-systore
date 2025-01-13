from odoo import models, fields, api
import requests
import inspect

class StockWebhook(models.Model):
    _inherit = 'stock.quant'

    @api.model
    # def create(self, vals):
    #     record = super(StockWebhook, self).create(vals)
    #     self._trigger_webhook(record)
    #     return record

    def write(self, vals):
        res = super(StockWebhook, self).write(vals)  # Only pass `vals` to super()
        for record in self:
            self._trigger_webhook(record)  # Trigger the webhook for each updated record
        return res


    def _trigger_webhook(self, record):
        
        if record.location_id.id != 28 or record.quantity == 0:
            return 
        webhook_url = "https://odoo.doto.com.mx/api/v2/odoo/hook/products/sync"
        payload = {
            "product_id": record.product_id.id,
            "product_sku": record.product_id.default_code,
            "stock": record.quantity,
            "location_id": record.location_id.id,
            "record_id" : record.id,
        }
        
        
        headers = {'Content-Type': 'application/json'}
        try:
            requests.post(webhook_url, json=payload, headers=headers)
        except Exception as e:
            self.env['ir.logging'].create({
                'name': 'Webhook Error',
                'type': 'server',
                'level': 'error',
                'message': str(e),
                'path': 'stock.quant._trigger_webhook',
                'func': '_trigger_webhook',
                'line': inspect.currentframe().f_lineno,
            })
