from odoo import api, fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    systore_resolved_supply_channel = fields.Selection(
        [
            ("wholesale", "Mayoreo"),
            ("retail", "Minorista"),
        ],
        string="Canal de compra",
        compute="_compute_systore_resolved_supply_channel",
        readonly=True,
    )

    @api.depends("name", "code", "lot_stock_id", "lot_stock_id.name", "lot_stock_id.complete_name")
    def _compute_systore_resolved_supply_channel(self):
        for warehouse in self:
            warehouse.systore_resolved_supply_channel = warehouse._systore_resolved_supply_channel()

    def _systore_resolved_supply_channel(self, location=None):
        self.ensure_one()
        prefixes = ("MXMAY", "SDMAY")
        warehouse_code = (self.code or "").strip().upper()
        warehouse_name = (self.name or "").strip().upper()
        target_location = location or self.lot_stock_id
        location_values = [
            (target_location.name or "").strip().upper() if target_location else "",
            (target_location.complete_name or "").strip().upper() if target_location else "",
        ]
        matches_prefix = warehouse_code.startswith(prefixes) or any(
            value.startswith(prefixes)
            or any(part.strip().startswith(prefixes) for part in value.split("/"))
            for value in location_values
        )
        matches_name = warehouse_name in ("MX: MAYOREO", "SAN DIEGO: MAYOREO")
        if matches_prefix or matches_name:
            return "wholesale"
        return "retail"
