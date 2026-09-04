# -*- coding: utf-8 -*-
from odoo import fields, models


class SystoreManualCost(models.Model):
    _name = 'systore.manual.cost'
    _description = 'Costo manual de respaldo - Analítica de ventas'
    _order = 'write_date desc, id desc'

    company_id = fields.Many2one('res.company', required=True, index=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    product_id = fields.Many2one('product.product', required=True, index=True, ondelete='cascade')
    lot_id = fields.Many2one('stock.lot', required=True, index=True, ondelete='cascade')
    unit_cost = fields.Monetary(string='Costo unitario manual', currency_field='currency_id', required=True)
    note = fields.Char(string='Motivo / referencia')
    assigned_by_id = fields.Many2one('res.users', string='Asignado por', readonly=True, default=lambda self: self.env.user)
    assigned_at = fields.Datetime(string='Fecha de asignación', readonly=True, default=fields.Datetime.now)

    _sql_constraints = [
        ('company_product_lot_unique', 'unique(company_id, product_id, lot_id)',
         'Ya existe un costo manual para este producto y lote.'),
    ]
