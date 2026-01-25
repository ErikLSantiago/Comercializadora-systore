from odoo import api, models

class StockMove(models.Model):
    _inherit = "stock.move"

    def _mc_reserved_qty_ml(self, ml):
        for fname in ("reserved_uom_qty", "quantity", "product_uom_qty"):
            if fname in ml._fields:
                return ml[fname] or 0.0
        return 0.0

    def _mc_auto_fill_serial_lots(self):
        """Cuando el producto es por serial, Odoo puede reservar sin asignar lot_id.
        Aquí autollenamos lot_id tomando seriales disponibles (FIFO por in_date) para que el precio por peso pueda calcularse.
        """
        Quant = self.env["stock.quant"]
        for move in self:
            line = move.sale_line_id
            if not line:
                continue
            tmpl = move.product_id.product_tmpl_id
            if not tmpl.x_use_weight_sale_price:
                continue
            if move.product_id.tracking != "serial":
                continue
            if not move.picking_id or move.picking_id.state in ("done", "cancel"):
                continue

            # move lines reservadas sin lot
            mls_to_fill = move.move_line_ids.filtered(
                lambda ml: not ml.lot_id and self._mc_reserved_qty_ml(ml) > 0
            )
            if not mls_to_fill:
                continue

            # Seriales disponibles en la ubicación de origen (FIFO)
            quants = Quant.search([
                ("product_id", "=", move.product_id.id),
                ("location_id", "child_of", move.location_id.id),
                ("lot_id", "!=", False),
                ("quantity", ">", 0),
            ], order="in_date,id")

            # Filtrar por disponibilidad real (si existe reserved_quantity)
            available_lots = []
            for q in quants:
                if "reserved_quantity" in q._fields:
                    if (q.quantity - q.reserved_quantity) <= 0:
                        continue
                available_lots.append(q.lot_id)
                if len(available_lots) >= len(mls_to_fill):
                    break

            # Asignar lot a cada move line reservada sin lot
            for ml, lot in zip(mls_to_fill, available_lots):
                ml.lot_id = lot.id

    def _action_assign(self, force_qty=False):
        res = super()._action_assign(force_qty=force_qty)

        # 1) Autollenar lot/serial para productos con precio por peso
        self._mc_auto_fill_serial_lots()

        # 2) Recalcular precio en las líneas de venta
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

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # No recalculamos aquí para evitar costo en confirmación masiva; lo hace _action_assign.
        return records
