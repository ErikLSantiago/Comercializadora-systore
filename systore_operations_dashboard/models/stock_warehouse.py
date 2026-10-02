from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    systore_operations_enabled = fields.Boolean(
        string='Participa en tablero de operaciones', copy=False,
        help='Habilita este almacén en el tablero. Debe asignar los usuarios autorizados.',
    )
    systore_operations_user_ids = fields.Many2many(
        'res.users', 'systore_operations_warehouse_user_rel', 'warehouse_id', 'user_id',
        string='Usuarios del tablero', copy=False,
        help='Solo estos usuarios pueden consultar este almacén desde el tablero.',
    )

    def _systore_check_configuration_access(self, vals):
        if ({'systore_operations_enabled', 'systore_operations_user_ids'} & vals.keys()
                and not self.env.su
                and not self.env.user.has_group('stock.group_stock_manager')):
            raise AccessError(_('Solo un administrador de Inventario puede configurar el tablero.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._systore_check_configuration_access(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._systore_check_configuration_access(vals)
        return super().write(vals)
