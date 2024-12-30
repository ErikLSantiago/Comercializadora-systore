from odoo import models, fields, api
import requests

class StockWebhook(models.Model):
    _inherit = 'stock.quant'

    @api.model
    def create(self, vals):
        record = super(StockWebhook, self).create(vals)
        self._trigger_webhook(record)
        return record

    def write(self, vals):
        res = super(StockWebhook, self).write(vals)
        for record in self:
            self._trigger_webhook(record)
        return res

    def _trigger_webhook(self, record):
        webhook_url = "https://webhook.site/fdc823f5-b01c-4748-a185-a1df92c48de6"
        payload = {
            "product_id": record.product_id.id,
            "product_sku": record.product_id.default_code,
            "stock": record.quantity,
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
