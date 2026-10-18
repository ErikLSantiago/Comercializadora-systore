from odoo import _
from odoo.exceptions import UserError


def pre_init_hook(env):
    old = env['ir.module.module'].sudo().search([
        ('name', 'in', ['systore_operations_dashboard', 'systore_operations_dasboard']),
        ('state', 'in', ['installed', 'to upgrade', 'to remove']),
    ], limit=1)
    if old:
        raise UserError(_('El módulo anterior sigue instalado. Migre su nombre técnico a operations_dashboard antes de instalar esta versión. Consulte MIGRATION.md; no desinstale el módulo anterior.'))
