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
    systore_operations_type_ids = fields.Many2many(
        'stock.picking.type', 'systore_operations_warehouse_type_rel', 'warehouse_id', 'type_id',
        string='Tipos de operación incluidos', compute='_compute_systore_operations_types',
        store=True, readonly=False, copy=False, compute_sudo=True, check_company=True,
        help='Marque los tipos que pueden aparecer en este almacén. Incluye tipos de otros almacenes '
             'de la misma compañía para los traslados que salen desde Existencias.',
    )

    @api.depends('company_id')
    def _compute_systore_operations_types(self):
        for warehouse in self:
            warehouse.systore_operations_type_ids = self.env['stock.picking.type'].search([
                ('company_id', '=', warehouse.company_id.id), ('active', '=', True),
            ])

    def _systore_check_configuration_access(self, vals):
        if ({'systore_operations_enabled', 'systore_operations_user_ids',
             'systore_operations_type_ids'} & vals.keys()
                and not self.env.su
                and not self.env.user.has_group('stock.group_stock_manager')):
            raise AccessError(_('Solo un administrador de Inventario puede configurar el tablero.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._systore_check_configuration_access(vals)
        warehouses = super().create(vals_list)
        # The native create builds the warehouse's operation types after creating
        # the warehouse record. Initialize our defaults after those types exist.
        for warehouse, vals in zip(warehouses, vals_list):
            if 'systore_operations_type_ids' not in vals:
                warehouse._compute_systore_operations_types()
        return warehouses

    def write(self, vals):
        self._systore_check_configuration_access(vals)
        return super().write(vals)
