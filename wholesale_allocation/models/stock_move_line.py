from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    is_manual_external_lot = fields.Boolean(
        string='Manual External Lot',
        compute='_compute_is_manual_external_lot',
        store=True,
        help='Checked when the selected lot does not belong to the associated purchase orders of the sale order.',
    )

    @api.depends('lot_id', 'picking_id.associated_purchase_order_ids', 'move_id.picking_id')
    def _compute_is_manual_external_lot(self):
        for line in self:
            picking = line.picking_id or line.move_id.picking_id
            if not picking or not picking.is_wholesale_allocation or not line.lot_id:
                line.is_manual_external_lot = False
                continue
            allowed_names = set(picking.associated_purchase_order_ids.mapped('name'))
            line.is_manual_external_lot = bool(allowed_names and line.lot_id.name not in allowed_names)

    def _wholesale_sale_order(self):
        """Return the sale order that originated this stock operation.

        Odoo multi-step delivery routes may expose the sale through the picking,
        the stock move's sale line, or the procurement group depending on the
        exact step. Keeping these fallbacks makes the lot-to-PO association work
        for MXMAY/PICK as well as the final delivery.
        """
        self.ensure_one()
        picking = self.picking_id or self.move_id.picking_id
        if not picking:
            return self.env['sale.order']

        sale = picking.sale_id
        if not sale and 'sale_line_id' in self.move_id._fields and self.move_id.sale_line_id:
            sale = self.move_id.sale_line_id.order_id
        if (
            not sale
            and picking.group_id
            and 'sale_id' in picking.group_id._fields
            and picking.group_id.sale_id
        ):
            sale = picking.group_id.sale_id
        return sale

    def _auto_link_wholesale_purchase_order_from_lot(self):
        """Link the PO represented by the selected lot to the originating sale.

        Business rule:
        - only Wholesale sales are affected;
        - lot name must exactly match purchase.order.name;
        - PO must belong to the same company and Wholesale warehouse;
        - cancelled POs are ignored;
        - if the PO is already linked, nothing is changed.

        This is intentionally executed after create/write of the move line.
        Automatic reservation is already restricted to linked POs, so a newly
        discovered PO here normally represents a user's manual lot override.
        """
        PurchaseOrder = self.env['purchase.order']

        for line in self:
            lot = line.lot_id
            if not lot or not lot.name:
                continue

            sale = line._wholesale_sale_order()
            if not sale or not sale.is_wholesale_allocation or not sale.warehouse_id:
                continue

            lot_name = lot.name.strip()
            if not lot_name:
                continue

            # Already linked: no extra lookup/write is necessary.
            if lot_name in set(sale.associated_purchase_order_ids.mapped('name')):
                continue

            po = PurchaseOrder.search([
                ('name', '=', lot_name),
                ('company_id', '=', sale.company_id.id),
                ('picking_type_id.warehouse_id', '=', sale.warehouse_id.id),
                ('state', '!=', 'cancel'),
            ], limit=1)
            if not po:
                continue

            sale.write({
                'associated_purchase_order_ids': [(4, po.id)],
            })

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._auto_link_wholesale_purchase_order_from_lot()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if 'lot_id' in vals:
            self._auto_link_wholesale_purchase_order_from_lot()
        return res
