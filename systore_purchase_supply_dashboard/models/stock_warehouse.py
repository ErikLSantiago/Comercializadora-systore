from odoo import api, fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    systore_supply_management = fields.Selection(
        [
            ("wholesale", "Mayoreo"),
            ("retail", "Minorista"),
            ("excluded", "Sin gestión para compras"),
        ],
        string="Gestión en abastecimiento",
        required=True,
        default="retail",
        index=True,
        help=(
            "Define el canal utilizado por el tablero. Los almacenes Sin gestión "
            "para compras se omiten de todos los análisis del módulo."
        ),
    )

    systore_resolved_supply_channel = fields.Selection(
        [
            ("wholesale", "Mayoreo"),
            ("retail", "Minorista"),
            ("excluded", "Sin gestión para compras"),
        ],
        string="Canal de compra",
        compute="_compute_systore_resolved_supply_channel",
        readonly=True,
    )

    @api.depends("systore_supply_management")
    def _compute_systore_resolved_supply_channel(self):
        for warehouse in self:
            warehouse.systore_resolved_supply_channel = warehouse.systore_supply_management

    def _systore_resolved_supply_channel(self, location=None):
        self.ensure_one()
        return self.systore_supply_management

    def _systore_is_managed_for_supply(self):
        self.ensure_one()
        return self.systore_supply_management != "excluded"

    def _systore_sync_supply_channel(self):
        for warehouse in self:
            channel = warehouse.systore_supply_management
            if channel not in ("wholesale", "retail"):
                continue
            for model_name in (
                "systore.supply.purchase.line",
                "systore.supply.demand.line",
                "systore.supply.trace.line",
            ):
                self.env[model_name].sudo().search([
                    ("warehouse_id", "=", warehouse.id),
                    ("channel", "!=", channel),
                ]).write({"channel": channel})

    def write(self, values):
        result = super().write(values)
        if "systore_supply_management" in values:
            self._systore_sync_supply_channel()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        warehouses = super().create(vals_list)
        for warehouse, values in zip(warehouses, vals_list):
            if "systore_supply_management" in values:
                continue
            code = (warehouse.code or "").strip().upper()
            name = (warehouse.name or "").strip().upper()
            if code.startswith(("MXMAY", "SDMAY")) or name in (
                "MX: MAYOREO", "SAN DIEGO: MAYOREO",
            ):
                warehouse.systore_supply_management = "wholesale"
        return warehouses
