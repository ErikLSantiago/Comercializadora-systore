# -*- coding: utf-8 -*-
from odoo import api, fields, models

class SystoreSalesChannel(models.Model):
    _name = 'systore.sales.channel'
    _description = 'Canal de venta Systore'
    _order = 'sequence, name'

    name = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    account_ids = fields.One2many('account.account', 'systore_sales_channel_id', string='Cuentas contables')
    _sql_constraints = [('name_unique', 'unique(name)', 'El canal de venta ya existe.')]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        mappings = {
            'Marketplace': {'401.01.01','401.01.03','401.01.04','401.01.04.01','401.01.05','401.01.06','401.01.07','401.01.08','401.01.13','401.01.14','401.01.15','401.01.20','401.01.21'},
            'Mayoreo': {'401.01.10','402.01.10'},
            'Empleado': {'401.01.12','401.01.16'},
        }
        for rec in records:
            codes = mappings.get(rec.name)
            if codes:
                self.env['account.account'].sudo().search([('code','in',list(codes)),('systore_sales_channel_id','=',False)]).write({'systore_sales_channel_id': rec.id})
        return records

    def init(self):
        # Conserva el mapeo histórico al introducir la configuración editable.
        mappings = {
            'Marketplace': ('401.01.01','401.01.03','401.01.04','401.01.04.01','401.01.05','401.01.06','401.01.07','401.01.08','401.01.13','401.01.14','401.01.15','401.01.20','401.01.21'),
            'Mayoreo': ('401.01.10','402.01.10'),
            'Empleado': ('401.01.12','401.01.16'),
        }
        for name, codes in mappings.items():
            channel = self.search([('name', '=', name)], limit=1)
            if channel:
                self.env['account.account'].sudo().search([('code', 'in', list(codes)), ('systore_sales_channel_id', '=', False)]).write({'systore_sales_channel_id': channel.id})

class ResUsers(models.Model):
    _inherit = 'res.users'

    systore_analytics_enabled = fields.Boolean(string='Puede ver Systore Analytics', default=False)
    systore_analytics_full_access = fields.Boolean(string='Ver reporte completo', default=False)
    systore_analytics_channel_ids = fields.Many2many('systore.sales.channel', 'systore_analytics_user_channel_rel', 'user_id', 'channel_id', string='Canales permitidos')
    systore_analytics_account_ids = fields.Many2many('account.account', 'systore_analytics_user_account_rel', 'user_id', 'account_id', string='Cuentas contables permitidas')
    systore_analytics_salesperson_ids = fields.Many2many('res.users', 'systore_analytics_user_salesperson_rel', 'user_id', 'salesperson_id', string='Vendedores permitidos')

    def write(self, vals):
        res = super().write(vals)
        if 'systore_analytics_enabled' in vals:
            group = self.env.ref('systore_sales_cost_analytics.group_systore_analytics_user', raise_if_not_found=False)
            if group:
                for user in self:
                    if user.systore_analytics_enabled:
                        user.sudo().write({'groups_id': [(4, group.id)]}) if group not in user.groups_id else None
                    elif group in user.groups_id and not user.has_group('systore_sales_cost_analytics.group_systore_analytics_manager'):
                        user.sudo().write({'groups_id': [(3, group.id)]})
        return res


class SystoreAnalyticsUserPermission(models.Model):
    _name = 'systore.analytics.user.permission'
    _description = 'Permisos de usuario Systore Analytics'
    _order = 'user_id'

    user_id = fields.Many2one('res.users', string='Usuario interno', required=True, ondelete='cascade', index=True, domain=[('share', '=', False), ('active', '=', True)])
    enabled = fields.Boolean(string='Puede ver el módulo')
    full_access = fields.Boolean(string='Ver reporte completo')
    channel_ids = fields.Many2many('systore.sales.channel', 'systore_perm_channel_rel', 'permission_id', 'channel_id', string='Canales permitidos')
    account_ids = fields.Many2many('account.account', 'systore_perm_account_rel', 'permission_id', 'account_id', string='Cuentas contables permitidas')
    salesperson_ids = fields.Many2many('res.users', 'systore_perm_salesperson_rel', 'permission_id', 'salesperson_id', string='Vendedores permitidos')
    _sql_constraints = [('user_unique', 'unique(user_id)', 'Ya existe una configuración para este usuario.')]

    def _sync_user(self):
        analytics_group = self.env.ref('systore_sales_cost_analytics.group_systore_analytics_user', raise_if_not_found=False)
        for rec in self:
            vals = {
                'systore_analytics_enabled': rec.enabled,
                'systore_analytics_full_access': rec.full_access,
                'systore_analytics_channel_ids': [(6, 0, rec.channel_ids.ids)],
                'systore_analytics_account_ids': [(6, 0, rec.account_ids.ids)],
                'systore_analytics_salesperson_ids': [(6, 0, rec.salesperson_ids.ids)],
            }
            rec.user_id.sudo().write(vals)
            if analytics_group:
                if rec.enabled and analytics_group not in rec.user_id.groups_id:
                    rec.user_id.sudo().write({'groups_id': [(4, analytics_group.id)]})
                elif not rec.enabled and analytics_group in rec.user_id.groups_id and not rec.user_id.has_group('systore_sales_cost_analytics.group_systore_analytics_manager'):
                    rec.user_id.sudo().write({'groups_id': [(3, analytics_group.id)]})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_user()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._sync_user()
        return res

