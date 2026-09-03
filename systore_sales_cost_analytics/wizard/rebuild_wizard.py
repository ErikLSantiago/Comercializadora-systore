# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class SystoreSalesCostRebuildWizard(models.TransientModel):
    _name = 'systore.sales.cost.rebuild.wizard'
    _description = 'Reconstruir analítica Systore'

    date_from = fields.Date(string='Desde', required=True, default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(string='Hasta', required=True, default=fields.Date.context_today)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    def action_rebuild(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_('La fecha Desde no puede ser posterior a Hasta.'))
        self.env['systore.sales.cost.line'].sudo().rebuild_range(self.date_from, self.date_to, self.company_id)
        action = self.env.ref('systore_sales_cost_analytics.action_systore_sales_cost_line').read()[0]
        action['domain'] = [
            ('company_id', '=', self.company_id.id),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
        ]
        action['context'] = {'search_default_group_account_type': 0}
        return action
