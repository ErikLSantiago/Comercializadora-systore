from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    systore_supply_channel = fields.Selection(
        [
            ("other", "Otro"),
            ("marketplace", "Marketplace"),
        ],
        string="Canal de abastecimiento",
        default="other",
        required=True,
        help=(
            "Identifica los almacenes Marketplace. Los almacenes marcados como "
            "Wholesale se clasifican automáticamente como Mayoreo."
        ),
    )

    def _systore_resolved_supply_channel(self):
        self.ensure_one()
        if self.is_wholesale:
            return "wholesale"
        if self.systore_supply_channel == "marketplace":
            return "marketplace"
        return "other"
