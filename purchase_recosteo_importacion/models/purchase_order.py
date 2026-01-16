# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    x_exchange_rate = fields.Float(string='Tipo de cambio', digits=(16, 6))
    x_last_recost_date = fields.Datetime(string='Último recosteo', readonly=True)
    x_last_recost_rate = fields.Float(string='TC último recosteo', digits=(16, 6), readonly=True)
    x_last_recost_user_id = fields.Many2one('res.users', string='Usuario último recosteo', readonly=True)

    def action_recostear(self):
        for order in self:
            if order.state not in ('draft', 'sent', 'to approve', 'purchase'):
                raise UserError(_('Solo se puede recostear en RFQ / Orden de compra.'))

            # Evitar recostear si ya hubo recepciones
            received_lines = order.order_line.filtered(lambda l: l.qty_received > 0)
            if received_lines:
                raise UserError(_(
                    'No se puede recostear porque ya hay cantidades recibidas.\n'
                    'Si necesitas ajustar costos después de recibir, considera landed costs o un ajuste contable según tu política.'
                ))

            rate = order.x_exchange_rate
            if not rate or rate <= 0:
                raise UserError(_('El Tipo de cambio debe ser mayor a 0 para recostear.'))

            for line in order.order_line:
                line._apply_recost(rate)

            order.x_last_recost_date = fields.Datetime.now()
            order.x_last_recost_rate = rate
            order.x_last_recost_user_id = self.env.user

        return True


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    order_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda OC',
        related='order_id.currency_id',
        readonly=True,
        store=False,
    )

    company_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda compañía',
        related='order_id.company_id.currency_id',
        readonly=True,
        store=False,
    )

    # Costos unitarios en moneda de la OC (usualmente USD)
    x_cost_gross_usd = fields.Monetary(
        string='Costo bruto (USD)',
        currency_field='order_currency_id',
        default=0.0,
    )
    x_cost_ship_usd = fields.Monetary(
        string='Costo envío (USD)',
        currency_field='order_currency_id',
        default=0.0,
    )

    # Importación fija unitária en moneda de la compañía (MXN)
    x_import_fixed_mxn = fields.Monetary(
        string='Costo importación (MXN)',
        currency_field='company_currency_id',
        default=0.0,
    )

    # Columnas informativas en MXN (calculadas con tipo de cambio del encabezado)
    x_cost_gross_mxn = fields.Monetary(
        string='Costo bruto (MXN)',
        currency_field='company_currency_id',
        compute='_compute_mxn_costs',
        store=True,
    )
    x_cost_ship_mxn = fields.Monetary(
        string='Costo envío (MXN)',
        currency_field='company_currency_id',
        compute='_compute_mxn_costs',
        store=True,
    )

    x_cost_total_mxn = fields.Monetary(
        string='Costo total (MXN)',
        currency_field='company_currency_id',
        compute='_compute_total_mxn',
        store=True,
    )

    @api.onchange('product_id')
    def _onchange_product_id_import_fixed(self):
        for line in self:
            if line.product_id:
                line.x_import_fixed_mxn = line.product_id.product_tmpl_id.x_import_fixed_mxn or 0.0

    @api.depends('x_cost_gross_usd', 'x_cost_ship_usd', 'order_id.x_exchange_rate')
    def _compute_mxn_costs(self):
        for line in self:
            rate = line.order_id.x_exchange_rate or 0.0
            if rate > 0:
                line.x_cost_gross_mxn = (line.x_cost_gross_usd or 0.0) * rate
                line.x_cost_ship_mxn = (line.x_cost_ship_usd or 0.0) * rate
            else:
                line.x_cost_gross_mxn = 0.0
                line.x_cost_ship_mxn = 0.0

    @api.depends('x_cost_gross_mxn', 'x_cost_ship_mxn', 'x_import_fixed_mxn')
    def _compute_total_mxn(self):
        for line in self:
            line.x_cost_total_mxn = (line.x_cost_gross_mxn or 0.0) + (line.x_cost_ship_mxn or 0.0) + (line.x_import_fixed_mxn or 0.0)

    def _apply_recost(self, rate):
        """Aplica el recosteo al price_unit nativo (moneda de la OC).

        Fórmula (unitaria):
        price_unit = costo_bruto_usd + costo_envio_usd + (import_mxn / tipo_cambio)
        """
        self.ensure_one()

        gross = self.x_cost_gross_usd or 0.0
        ship = self.x_cost_ship_usd or 0.0
        import_mxn = self.x_import_fixed_mxn or 0.0

        if not rate or rate <= 0:
            raise UserError(_('El Tipo de cambio debe ser mayor a 0 para recostear.'))

        import_in_order_currency = import_mxn / rate if import_mxn else 0.0
        new_price_unit = gross + ship + import_in_order_currency

        # Actualiza solo el price_unit; Odoo recalcula el resto.
        self.price_unit = new_price_unit
