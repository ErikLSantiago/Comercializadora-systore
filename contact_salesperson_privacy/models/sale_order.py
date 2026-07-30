from odoo import api, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _privacy_partners(self):
        partners = self.env["res.partner"]
        for order in self:
            order_partners = (
                order.partner_id
                | order.partner_invoice_id
                | order.partner_shipping_id
            )
            partners |= order_partners | order_partners.mapped("commercial_partner_id")
        return partners

    def _sync_contact_privacy_users(self):
        """Set the responsible seller and preserve every historical authorization."""
        for order in self.sudo().filtered(lambda item: item.user_id):
            partners = order._privacy_partners()
            partners.write({
                "user_id": order.user_id.id,
                "contact_allowed_user_ids": [(4, order.user_id.id)],
            })

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._sync_contact_privacy_users()
        return orders

    def write(self, vals):
        result = super().write(vals)
        if {"user_id", "partner_id", "partner_invoice_id", "partner_shipping_id"} & set(vals):
            self._sync_contact_privacy_users()
        return result

    def action_confirm(self):
        result = super().action_confirm()
        self._sync_contact_privacy_users()
        return result
