# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import Command, api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    can_merge_products = fields.Boolean(
        string="Puede fusionar productos / SKU",
        compute="_compute_can_merge_products",
        inverse="_inverse_can_merge_products",
        help="Permite ver y ejecutar la acción Fusionar productos.",
    )

    @api.depends("groups_id")
    def _compute_can_merge_products(self):
        merge_group = self.env.ref(
            "base_product_merge.res_group_merge_duplicate_product",
            raise_if_not_found=False,
        )
        for user in self:
            user.can_merge_products = bool(merge_group and merge_group in user.groups_id)

    def _inverse_can_merge_products(self):
        merge_group = self.env.ref(
            "base_product_merge.res_group_merge_duplicate_product"
        )
        for user in self:
            command = (
                Command.link(merge_group.id)
                if user.can_merge_products
                else Command.unlink(merge_group.id)
            )
            user.write({"groups_id": [command]})
