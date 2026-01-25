from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_open_weight_price_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Asignar seriales y recalcular"),
            "res_model": "mc.weight.price.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_sale_order_id": self.id,
                # pick a default line if only one eligible
                "default_line_id": (self.order_line.filtered(lambda l: l.product_id.product_tmpl_id.x_use_weight_sale_price)[:1].id or False),
            },
        }
