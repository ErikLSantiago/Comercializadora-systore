from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    x_reserved_serial_count = fields.Integer(
        string="Seriales reservados",
        compute="_compute_x_reserved_serial_count",
        help="Suma de seriales/lotes reservados en las líneas.",
    )

    @api.depends("order_line.x_reserved_serial_count")
    def _compute_x_reserved_serial_count(self):
        for order in self:
            order.x_reserved_serial_count = sum(order.order_line.mapped("x_reserved_serial_count"))


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
