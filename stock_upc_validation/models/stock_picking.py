from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    systore_upc_picking_validated = fields.Boolean(
        string='UPC/EAN validado en recolección',
        copy=False,
        readonly=True,
    )
    systore_require_tracking_on_pack = fields.Boolean(
        string='Exigir guía en empaque',
        related='picking_type_id.systore_require_tracking_on_pack',
        readonly=True,
    )

    def button_validate(self):
        # Recepción: primero conserva el flujo de registro UPC/EAN.
        # Recolección/Empaque: el wizard de UPC/EAN también puede capturar la guía,
        # por eso debe abrirse antes que el wizard independiente de guía.
        if self.env.context.get('systore_skip_upc_receipt_wizard'):
            result = super().button_validate()
            self._systore_propagate_pack_tracking_to_outgoing()
            return result

        pickings_to_check = self.filtered(lambda p: p._systore_needs_upc_receipt_wizard())
        if pickings_to_check:
            picking = pickings_to_check[0]
            wizard = self.env['stock.receipt.upc.wizard'].create_from_picking(picking)
            return {
                'name': _('Registrar UPC/EAN de recepción'),
                'type': 'ir.actions.act_window',
                'res_model': 'stock.receipt.upc.wizard',
                'view_mode': 'form',
                'target': 'new',
                'res_id': wizard.id,
            }

        if not self.env.context.get('systore_skip_upc_picking_wizard'):
            pickings_to_validate = self.filtered(lambda p: p._systore_needs_upc_picking_wizard())
            if pickings_to_validate:
                picking = pickings_to_validate[0]
                wizard = self.env['stock.picking.upc.wizard'].create_from_picking(picking)
                return {
                    'name': _('Validar UPC/EAN de recolección'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'stock.picking.upc.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'res_id': wizard.id,
                }

        # Si un tipo de operación de empaque no exige UPC/EAN pero sí guía,
        # se conserva el wizard simple de guía como respaldo.
        if not self.env.context.get('systore_skip_pack_tracking_wizard'):
            tracking_pickings = self.filtered(lambda p: p._systore_needs_pack_tracking_wizard())
            if tracking_pickings:
                picking = tracking_pickings[0]
                wizard = self.env['stock.pack.tracking.wizard'].create({'picking_id': picking.id})
                return {
                    'name': _('Capturar número de guía'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'stock.pack.tracking.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'res_id': wizard.id,
                }

        result = super().button_validate()
        self._systore_propagate_pack_tracking_to_outgoing()
        return result

    def _systore_needs_upc_receipt_wizard(self):
        self.ensure_one()
        if self.picking_type_id.code != 'incoming':
            return False
        if not self.picking_type_id.systore_require_upc_on_receipt:
            return False
        if self.state in ('done', 'cancel'):
            return False
        products = self._systore_receipt_products_to_validate()
        return bool(products)

    def _systore_receipt_products_to_validate(self):
        self.ensure_one()
        products = self.env['product.product']
        for move in self.move_ids_without_package.filtered(lambda m: m.state not in ('done', 'cancel')):
            if move.product_id and move.product_id.type in ('product', 'consu'):
                products |= move.product_id
        return products

    def _systore_needs_upc_picking_wizard(self):
        self.ensure_one()
        if self.picking_type_id.code == 'incoming':
            return False
        if not self.picking_type_id.systore_require_upc_on_picking:
            return False
        if self.systore_upc_picking_validated:
            return False
        if self.state in ('done', 'cancel'):
            return False
        return bool(self._systore_picking_products_to_validate())

    def _systore_picking_products_to_validate(self):
        self.ensure_one()
        products = self.env['product.product']
        for move in self.move_ids_without_package.filtered(lambda m: m.state not in ('done', 'cancel')):
            if not move.product_id or move.product_id.type not in ('product', 'consu'):
                continue
            qty = self._systore_move_effective_qty(move)
            if float_is_zero(qty, precision_rounding=move.product_uom.rounding):
                continue
            products |= move.product_id
        return products

    def _systore_move_effective_qty(self, move):
        """Return the quantity that is being advanced/validated in a version-safe way."""
        qty = 0.0
        for ml in move.move_line_ids:
            if 'quantity' in ml._fields:
                qty += ml.quantity or 0.0
            elif 'qty_done' in ml._fields:
                qty += ml.qty_done or 0.0
        if not qty:
            if 'quantity' in move._fields:
                qty = move.quantity or 0.0
            elif 'quantity_done' in move._fields:
                qty = move.quantity_done or 0.0
            elif 'qty_done' in move._fields:
                qty = move.qty_done or 0.0
        if not qty:
            qty = move.product_uom_qty or 0.0
        return qty

    def _systore_needs_pack_tracking_wizard(self):
        self.ensure_one()
        if self.state in ('done', 'cancel'):
            return False
        if not self.picking_type_id.systore_require_tracking_on_pack:
            return False
        return not bool((self.carrier_tracking_ref or '').strip())

    def _systore_propagate_pack_tracking_to_outgoing(self):
        for picking in self:
            tracking = (picking.carrier_tracking_ref or '').strip()
            if not tracking or not picking.picking_type_id.systore_require_tracking_on_pack:
                continue

            next_pickings = picking.move_ids.move_dest_ids.mapped('picking_id').filtered(
                lambda p: p and p.id != picking.id and p.state not in ('done', 'cancel')
            )
            if not next_pickings:
                # Fallback for chained transfers where the destination picking is linked by group/origin.
                domain = [
                    ('id', '!=', picking.id),
                    ('state', 'not in', ('done', 'cancel')),
                    ('group_id', '=', picking.group_id.id if picking.group_id else False),
                    ('origin', '=', picking.origin or picking.name),
                ]
                next_pickings = self.search(domain)

            for next_picking in next_pickings:
                vals = {'carrier_tracking_ref': tracking}
                if next_picking.name and not next_picking.name.endswith('-%s' % tracking):
                    vals['name'] = '%s-%s' % (next_picking.name, tracking)
                next_picking.write(vals)
