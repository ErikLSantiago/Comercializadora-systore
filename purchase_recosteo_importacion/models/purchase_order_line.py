from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    # Captura (unitario)
    x_gross_usd = fields.Float(string='Costo bruto (USD)', digits=(16, 6), default=0.0)
    x_ship_usd = fields.Float(string='Costo envío (USD)', digits=(16, 6), default=0.0)

    # Importación (unitario, MXN) - se llena desde el producto
    x_import_mxn = fields.Monetary(
        string='Costo importación (MXN)',
        currency_field='currency_id',
        default=0.0,
        help='Costo unitario fijo de importación en MXN. Se sugiere desde el producto al seleccionarlo.',
    )

    # Cálculos (unitario, MXN)
    x_gross_mxn = fields.Monetary(
        string='Costo bruto (MXN)',
        currency_field='currency_id',
        compute='_compute_cost_breakdown_mxn',
        store=True,
        readonly=True,
    )

    x_ship_mxn = fields.Monetary(
        string='Costo envío (MXN)',
        currency_field='currency_id',
        compute='_compute_cost_breakdown_mxn',
        store=True,
        readonly=True,
    )

    x_calc_price_mxn = fields.Monetary(
        string='Precio calculado (MXN)',
        currency_field='currency_id',
        compute='_compute_cost_breakdown_mxn',
        store=True,
        readonly=True,
        help='Suma unitaria: bruto_mxn + envío_mxn + importación_mxn.',
    )

    @api.depends('x_gross_usd', 'x_ship_usd', 'x_import_mxn', 'order_id.x_exchange_rate')
    def _compute_cost_breakdown_mxn(self):
        for line in self:
            rate = line.order_id.x_exchange_rate or 0.0
            line.x_gross_mxn = (line.x_gross_usd or 0.0) * rate
            line.x_ship_mxn = (line.x_ship_usd or 0.0) * rate
            line.x_calc_price_mxn = (line.x_gross_mxn or 0.0) + (line.x_ship_mxn or 0.0) + (line.x_import_mxn or 0.0)

    @api.onchange('product_id')
    def _onchange_product_id_set_import_cost(self):
        for line in self:
            if not line.product_id:
                continue
            tmpl = line.product_id.product_tmpl_id
            line.x_import_mxn = tmpl.x_import_fixed_mxn or 0.0

    @api.model_create_multi
    def create(self, vals_list):
        Product = self.env['product.product']
        for vals in vals_list:
            if vals.get('product_id') and 'x_import_mxn' not in vals:
                product = Product.browse(vals['product_id'])
                vals['x_import_mxn'] = product.product_tmpl_id.x_import_fixed_mxn or 0.0
        return super().create(vals_list)

    def write(self, vals):
        # Si cambian el producto y no mandan import_mxn explícito, sugerimos el del producto
        if 'product_id' in vals and 'x_import_mxn' not in vals:
            product = self.env['product.product'].browse(vals['product_id'])
            vals = dict(vals)
            vals['x_import_mxn'] = product.product_tmpl_id.x_import_fixed_mxn or 0.0
        return super().write(vals)
