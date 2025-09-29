# -*- coding: utf-8 -*-
import secrets
import hmac

from odoo import api, fields, models, _
from odoo.exceptions import AccessDenied

class ResUsers(models.Model):
    _inherit = "res.users"

    api_token = fields.Char(
        string="API Token",
        help=(
            "Token alternativo para autenticación externa (XML-RPC/JSON-RPC). "
            "Úsalo como si fuera la contraseña en sistemas de integración."
        ),
        groups="base.group_system",
        copy=False,
    )

    def action_generate_api_token(self):
        """Genera un token aleatorio y lo guarda en el usuario."""
        self.ensure_one()
        token = secrets.token_urlsafe(40)
        self.api_token = token
        msg = _(
            "Se generó un nuevo API Token para el usuario '%s'.\n\n"
            "Cópialo ahora y guárdalo de forma segura:\n\n%s\n\n"
            "Úsalo como contraseña en tus integraciones (p. ej. Inventory Planner)."
        ) % (self.name, token)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("API Token generado"),
                "message": msg,
                "sticky": True,
                "type": "warning",
            },
        }

    def _check_credentials(self, password, user_agent_env):
        # Primero intentamos la verificación estándar (password normal).
        try:
            return super()._check_credentials(password, user_agent_env)
        except AccessDenied:
            # Si falló, permitir autenticación por API Token.
            self.ensure_one()
            if (self.api_token or "") and (password or "") and hmac.compare_digest(self.api_token, password):
                return  # autenticación aceptada con token
            # Mantener el AccessDenied original si tampoco coincide el token.
            raise
