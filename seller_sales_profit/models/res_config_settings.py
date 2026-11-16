from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    seller_sales_profit_company_id = fields.Many2one(
        "res.company",
        string="Empresa del tablero de comisiones",
        config_parameter="seller_sales_profit.company_id",
    )
