from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    x_vendor_shipping_id = fields.Many2one(
        related="company_id.x_vendor_shipping_id",
        readonly=False,
    )
    x_vendor_import_id = fields.Many2one(
        related="company_id.x_vendor_import_id",
        readonly=False,
    )
    x_product_shipping_id = fields.Many2one(
        related="company_id.x_product_shipping_id",
        readonly=False,
    )
    x_product_import_id = fields.Many2one(
        related="company_id.x_product_import_id",
        readonly=False,
    )
