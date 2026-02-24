import re
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class AccountAccount(models.Model):
    _inherit = "account.account"

    financial_group_id = fields.Many2one(
            "account.financial.group",
            string="Grupo financiero",
            help="Grupo para segmentar reportes (P&L / Balance).",
            tracking=True,
        )

    financial_group_locked = fields.Boolean(
        string="Bloquear edición de grupo",
        default=False,
        help="Si está activo, el usuario no puede cambiar el grupo manualmente.",
    )

def _fin_group_company(self):
    """Return the company record to use for grouping rules.

    Odoo 18 en algunas localizaciones puede no exponer company_id en account.account
    durante validación de vistas. Soportamos company_id o company_ids.
    """
    self.ensure_one()
    if "company_id" in self._fields and self.company_id:
        return self.company_id
    if "company_ids" in self._fields and self.company_ids:
        return self.company_ids[0]
    return self.env.company

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        # Auto-assign on create if empty
        recs._auto_assign_financial_group(force=False)
        return recs

    def write(self, vals):
        # Prevent manual change when locked (unless context allows)
        if "financial_group_id" in vals and not self.env.context.get("allow_fin_group_write"):
            locked = self.filtered("financial_group_locked")
            if locked:
                raise ValidationError(_("El grupo financiero está bloqueado. Desactiva 'Bloquear edición de grupo' o usa la acción de recomputo."))
        res = super().write(vals)
        # Auto-reassign if code/name/type changed
        if any(k in vals for k in ("code", "name", "account_type", "company_id")):
            self._auto_assign_financial_group(force=False)
        return res

    def _auto_assign_financial_group(self, force=False):
        """Assign financial_group_id based on rules. If force=True, overwrite existing group."""
        Rule = self.env["account.financial.group.rule"]
        for acc in self:
            if not acc._fin_group_company():
                continue
            if not force and acc.financial_group_id:
                continue

            rules = Rule.search([
                ("company_id", "=", acc._fin_group_company().id),
                ("active", "=", True),
            ], order="sequence, id")

            chosen = False
            for r in rules:
                if r.rule_type == "domain":
                    try:
                        dom = eval(r.domain, {"__builtins__": {}}, {})
                    except Exception:
                        continue
                    dom = list(dom) + [("id", "=", acc.id)]
                    if self.search_count(dom):
                        acc.with_context(allow_fin_group_write=True).financial_group_id = r.group_id.id
                        chosen = True
                elif r.rule_type == "code_prefix":
                    if acc.code and r.code_prefix and acc.code.startswith(r.code_prefix):
                        acc.with_context(allow_fin_group_write=True).financial_group_id = r.group_id.id
                        chosen = True
                elif r.rule_type == "code_regex":
                    if acc.code and r.code_regex:
                        try:
                            if re.search(r.code_regex, acc.code):
                                acc.with_context(allow_fin_group_write=True).financial_group_id = r.group_id.id
                                chosen = True
                        except re.error:
                            continue
                elif r.rule_type == "name_contains":
                    if acc.name and r.name_contains and r.name_contains.lower() in acc.name.lower():
                        acc.with_context(allow_fin_group_write=True).financial_group_id = r.group_id.id
                        chosen = True
                elif r.rule_type == "account_type":
                    if acc.account_type and r.account_type and acc.account_type == r.account_type:
                        acc.with_context(allow_fin_group_write=True).financial_group_id = r.group_id.id
                        chosen = True

                if chosen and r.stop_at_first_match:
                    break
