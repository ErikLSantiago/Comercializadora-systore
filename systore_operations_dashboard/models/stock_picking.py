from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    systore_operations_purchase_ids = fields.Many2many(
        'purchase.order', 'systore_operations_picking_purchase_rel', 'picking_id', 'purchase_id',
        string='Compras vinculadas', compute='_compute_systore_operations_purchases',
        store=True, compute_sudo=True, readonly=True,
    )
    systore_operations_expected_date = fields.Datetime(
        string='Fecha esperada OC', compute='_compute_systore_operations_purchase_info',
        store=True, compute_sudo=True,
    )
    systore_operations_purchase_names = fields.Char(
        string='Órdenes de compra', compute='_compute_systore_operations_purchase_info',
        store=True, compute_sudo=True,
    )
    systore_operations_packages = fields.Integer(
        string='Bultos OC', compute='_compute_systore_operations_purchase_info',
        store=True, compute_sudo=True,
        help='Total informado en las compras vinculadas. Puede repetirse en operaciones de la misma compra.',
    )
    systore_operations_supplier_refs = fields.Char(
        string='Referencia del proveedor', compute='_compute_systore_operations_purchase_info',
        store=True, compute_sudo=True,
    )
    systore_operations_pieces = fields.Float(
        string='Piezas OC', digits='Product Unit of Measure',
        compute='_compute_systore_operations_purchase_info', store=True, compute_sudo=True,
    )
    systore_operations_sale_names = fields.Char(
        string='Orden de venta', compute='_compute_systore_operations_sales',
        store=True, compute_sudo=True,
    )

    @api.depends('sale_id.name', 'move_ids.sale_line_id.order_id.name',
                 'move_ids.move_orig_ids.sale_line_id.order_id.name',
                 'move_ids.move_orig_ids.move_orig_ids.sale_line_id.order_id.name')
    def _compute_systore_operations_sales(self):
        for picking in self:
            orders = picking.sale_id | picking.move_ids.sale_line_id.order_id
            moves = picking.move_ids
            for _level in range(2):
                moves = moves.move_orig_ids
                orders |= moves.sale_line_id.order_id
            picking.systore_operations_sale_names = ', '.join(sorted(orders.mapped('name')))

    @api.depends(
        'move_ids.purchase_line_id.order_id',
        'move_ids.move_orig_ids.purchase_line_id.order_id',
        'move_ids.move_orig_ids.move_orig_ids.purchase_line_id.order_id',
    )
    def _compute_systore_operations_purchases(self):
        # Follow native move links, never parse the free-text origin or lot name.
        # Two upstream levels also cover a native three-step receipt.
        for picking in self:
            moves = picking.move_ids
            orders = moves.purchase_line_id.order_id
            for _level in range(2):
                moves = moves.move_orig_ids
                orders |= moves.purchase_line_id.order_id
            picking.systore_operations_purchase_ids = orders

    @api.depends(
        'systore_operations_purchase_ids',
        'systore_operations_purchase_ids.name',
        'systore_operations_purchase_ids.date_planned',
        'systore_operations_purchase_ids.systore_expected_packages',
        'systore_operations_purchase_ids.partner_ref',
        'systore_operations_purchase_ids.systore_operations_pieces',
    )
    def _compute_systore_operations_purchase_info(self):
        for picking in self:
            orders = picking.systore_operations_purchase_ids
            dates = [date for date in orders.mapped('date_planned') if date]
            picking.systore_operations_expected_date = min(dates) if dates else False
            picking.systore_operations_purchase_names = ', '.join(orders.mapped('name'))
            picking.systore_operations_packages = sum(orders.mapped('systore_expected_packages'))
            picking.systore_operations_supplier_refs = ', '.join(
                sorted({ref for ref in orders.mapped('partner_ref') if ref}))
            picking.systore_operations_pieces = sum(orders.mapped('systore_operations_pieces'))
