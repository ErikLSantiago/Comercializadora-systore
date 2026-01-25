from odoo import models

class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_assign(self):
        res = super()._action_assign()
        sale_lines = self.mapped("sale_line_id").filtered(lambda l: l)
        for line in sale_lines:
            line._mc_recompute_price_from_reserved_serials()
        return res

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def write(self, vals):
        res = super().write(vals)
        trigger_fields = {"lot_id", "reserved_uom_qty", "quantity", "product_uom_qty"}
        if trigger_fields.intersection(vals.keys()):
            sale_lines = self.mapped("move_id.sale_line_id").filtered(lambda l: l)
            for line in sale_lines:
                line._mc_recompute_price_from_reserved_serials()
        return res

    @classmethod
    def create(cls, vals_list):
        records = super().create(vals_list)
        sale_lines = records.mapped("move_id.sale_line_id").filtered(lambda l: l)
        for line in sale_lines:
            line._mc_recompute_price_from_reserved_serials()
        return records
