from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    contact_privacy_profile = fields.Selection(
        selection=[
            ("none", "Sin perfil"),
            ("restricted", "Restringido: solo contactos asignados"),
            ("alpha", "Alfa: todos los contactos"),
        ],
        string="Perfil de privacidad de contactos",
        compute="_compute_contact_privacy_profile",
        inverse="_inverse_contact_privacy_profile",
        help=(
            "Restringido permite ver únicamente contactos asignados. "
            "Alfa permite consultar y administrar toda la base de contactos."
        ),
    )

    @api.depends("groups_id")
    def _compute_contact_privacy_profile(self):
        restricted_group = self.env.ref(
            "contact_salesperson_privacy.group_contact_privacy_restricted",
            raise_if_not_found=False,
        )
        alpha_group = self.env.ref(
            "contact_salesperson_privacy.group_contact_privacy_all",
            raise_if_not_found=False,
        )
        for user in self:
            if alpha_group and alpha_group in user.groups_id:
                user.contact_privacy_profile = "alpha"
            elif restricted_group and restricted_group in user.groups_id:
                user.contact_privacy_profile = "restricted"
            else:
                user.contact_privacy_profile = "none"

    def _inverse_contact_privacy_profile(self):
        restricted_group = self.env.ref(
            "contact_salesperson_privacy.group_contact_privacy_restricted"
        )
        alpha_group = self.env.ref(
            "contact_salesperson_privacy.group_contact_privacy_all"
        )
        for user in self:
            commands = [
                (3, restricted_group.id),
                (3, alpha_group.id),
            ]
            if user.contact_privacy_profile == "restricted":
                commands.append((4, restricted_group.id))
            elif user.contact_privacy_profile == "alpha":
                commands.append((4, alpha_group.id))
            user.write({"groups_id": commands})
