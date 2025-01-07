from odoo import models, fields, api
import requests

class StockWebhook(models.Model):
    _inherit = 'stock.quant'

    @api.model
    # def create(self, vals):
    #     record = super(StockWebhook, self).create(vals)
    #     self._trigger_webhook(record)
    #     return record

    def write(self, vals):
        res = super(StockWebhook, self).write(vals)
        records_to_trigger = self.filtered(lambda r: r.location_id.id == 28 and 'quantity' in vals)
        for record in records_to_trigger:
            self._trigger_webhook(record)
        return res

    def _trigger_webhook(self, record):
        
        webhook_url = "https://webhook.site/f938beda-7b83-4c7e-9d74-4ef36909f29c"
        payload = {
            "product_id": record.product_id.id,
            "product_sku": record.product_id.default_code,
            "stock": record.quantity,
            "location_id": record.location_id.id,
            "record_id" : record.id
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
            })
