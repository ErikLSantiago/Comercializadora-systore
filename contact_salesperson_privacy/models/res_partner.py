from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    contact_is_restricted = fields.Boolean(
        string="Contacto restringido",
        default=True,
        help=(
            "Campo conservado por compatibilidad. La visibilidad de los usuarios "
            "restringidos se controla siempre mediante asignaciones."
        ),
        tracking=True,
    )
    contact_allowed_user_ids = fields.Many2many(
        comodel_name="res.users",
        relation="res_partner_contact_allowed_user_rel",
        column1="partner_id",
        column2="user_id",
        string="Usuarios autorizados",
        domain=[("share", "=", False)],
        help="Usuarios que pueden consultar este contacto restringido.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Make a contact created by a restricted seller immediately theirs."""
        current_user = self.env.user
        is_restricted = current_user.has_group(
            "contact_salesperson_privacy.group_contact_privacy_restricted"
        )
        is_alpha = current_user.has_group(
            "contact_salesperson_privacy.group_contact_privacy_all"
        )
        if is_restricted and not is_alpha:
            prepared_vals_list = []
            for values in vals_list:
                values = dict(values)
                values["user_id"] = current_user.id
                values["contact_allowed_user_ids"] = [(4, current_user.id)]
                prepared_vals_list.append(values)
            vals_list = prepared_vals_list

        partners = super().create(vals_list)

        if is_restricted and not is_alpha:
            commercial_partners = partners.mapped("commercial_partner_id") - partners
            if commercial_partners:
                commercial_partners.sudo().write({
                    "user_id": current_user.id,
                    "contact_allowed_user_ids": [(4, current_user.id)],
                })
        return partners
