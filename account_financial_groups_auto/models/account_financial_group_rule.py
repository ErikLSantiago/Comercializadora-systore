from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountFinancialGroupRule(models.Model):
    _name = "account.financial.group.rule"
    _description = "Financial Group Auto-Assignment Rule"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    group_id = fields.Many2one("account.financial.group", required=True, ondelete="cascade")
    apply_on = fields.Selection([("account", "Cuenta contable")], default="account", required=True)

    rule_type = fields.Selection(
        [
            ("code_prefix", "Prefijo de código (ej. 610)"),
            ("code_regex", "Regex de código (ej. ^61\\d{2}$)"),
            ("name_contains", "Nombre contiene"),
            ("account_type", "Tipo de cuenta (expense/income/asset/...)"),
            ("domain", "Dominio Odoo avanzado (expertos)"),
        ],
        default="code_prefix",
        required=True,
    )

    code_prefix = fields.Char(help="Ej: 610 o 6001. Coincide si account.code inicia con este prefijo.")
    code_regex = fields.Char(help="Regex Python, ej: ^61\d{2}$")
    name_contains = fields.Char(help="Ej: 'Paqueter' (no sensible a mayúsculas)")
    account_type = fields.Selection(selection=lambda self: self.env["account.account"]._fields["account_type"].selection)
    domain = fields.Char(help="Dominio Odoo para account.account, ej: [('account_type','=','expense'),('code','=like','61%%')]")

    stop_at_first_match = fields.Boolean(default=True, help="Si coincide, no evalúa reglas posteriores.")

    _sql_constraints = [
        ("name_company_uniq", "unique(name, company_id)", "Ya existe una regla con este nombre en la compañía."),
    ]

    @api.constrains("rule_type", "code_prefix", "code_regex", "name_contains", "account_type", "domain")
    def _check_rule_fields(self):
        for r in self:
            if r.rule_type == "code_prefix" and not r.code_prefix:
                raise ValidationError(_("Define un prefijo de código."))
            if r.rule_type == "code_regex" and not r.code_regex:
                raise ValidationError(_("Define un regex de código."))
            if r.rule_type == "name_contains" and not r.name_contains:
                raise ValidationError(_("Define el texto a buscar en el nombre."))
            if r.rule_type == "account_type" and not r.account_type:
                raise ValidationError(_("Selecciona un tipo de cuenta."))
            if r.rule_type == "domain" and not r.domain:
                raise ValidationError(_("Define el dominio avanzado."))

    def _match_accounts_domain(self):
        """Return a domain to find matching account.account records.

        Nota: en algunas localizaciones de Odoo 18, account.account usa company_ids en lugar de company_id.
        """
        self.ensure_one()
        Account = self.env["account.account"]

        if self.rule_type == "domain":
            try:
                dom = eval(self.domain, {"__builtins__": {}}, {})
            except Exception as e:
                raise ValidationError(_("Dominio inválido: %s") % e)
            return dom

        dom = []
        if "company_id" in Account._fields:
            dom.append(("company_id", "=", self.company_id.id))
        elif "company_ids" in Account._fields:
            dom.append(("company_ids", "in", self.company_id.id))

        if self.rule_type == "account_type":
            dom.append(("account_type", "=", self.account_type))

        return dom
