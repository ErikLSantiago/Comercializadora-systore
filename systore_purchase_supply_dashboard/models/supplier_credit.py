from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _default_supplier_credit_currency(self):
        return self.env.ref("base.USD", raise_if_not_found=False) or self.env.company.currency_id

    systore_supplier_credit_enabled = fields.Boolean(
        string="Otorga crédito",
        tracking=True,
        help="Indica que el proveedor tiene una línea de crédito disponible.",
    )
    systore_supplier_credit_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda del crédito",
        default=_default_supplier_credit_currency,
        tracking=True,
    )
    systore_supplier_credit_limit = fields.Monetary(
        string="Límite de crédito de proveedor",
        currency_field="systore_supplier_credit_currency_id",
        tracking=True,
    )
    systore_supplier_credit_used = fields.Monetary(
        string="Crédito utilizado",
        currency_field="systore_supplier_credit_currency_id",
        compute="_compute_systore_supplier_credit_usage",
        compute_sudo=True,
    )
    systore_supplier_credit_available = fields.Monetary(
        string="Crédito disponible",
        currency_field="systore_supplier_credit_currency_id",
        compute="_compute_systore_supplier_credit_usage",
        compute_sudo=True,
    )
    systore_supplier_credit_overdue = fields.Monetary(
        string="Saldo vencido",
        currency_field="systore_supplier_credit_currency_id",
        compute="_compute_systore_supplier_credit_usage",
        compute_sudo=True,
    )
    systore_supplier_credit_utilization = fields.Float(
        string="Utilización (%)",
        compute="_compute_systore_supplier_credit_usage",
        compute_sudo=True,
        digits=(5, 2),
    )

    def _systore_supplier_credit_position(self, currency=None, company=None):
        self.ensure_one()
        company = company or self.env.company
        target_currency = (
            currency
            or self.systore_supplier_credit_currency_id
            or company.currency_id
        )
        orders = self.env["purchase.order"].sudo().search([
            ("company_id", "=", company.id),
            ("partner_id", "=", self.id),
            ("state", "in", ["purchase", "done"]),
            ("systore_purchase_condition", "=", "credit"),
        ])
        orders = orders.filtered(lambda order: (
            order.picking_type_id.warehouse_id
            and order.picking_type_id.warehouse_id._systore_is_managed_for_supply()
        ))
        today = fields.Date.context_today(self)
        used = overdue = 0.0
        for order in orders:
            balance = order._systore_credit_balance_in_currency(target_currency)
            used += balance
            if order.systore_credit_due_date and order.systore_credit_due_date < today:
                overdue += balance
        return {"used": used, "overdue": overdue, "orders": orders}

    def _compute_systore_supplier_credit_usage(self):
        for partner in self:
            currency = partner.systore_supplier_credit_currency_id or self.env.company.currency_id
            position = partner._systore_supplier_credit_position(
                currency, company=self.env.company
            )
            used = position["used"]
            overdue = position["overdue"]
            limit_amount = partner.systore_supplier_credit_limit or 0.0
            partner.systore_supplier_credit_used = used
            partner.systore_supplier_credit_available = limit_amount - used
            partner.systore_supplier_credit_overdue = overdue
            partner.systore_supplier_credit_utilization = (
                used / limit_amount * 100.0 if limit_amount else 0.0
            )

    @api.constrains("systore_supplier_credit_limit")
    def _check_systore_supplier_credit_configuration(self):
        for partner in self:
            if partner.systore_supplier_credit_limit < 0:
                raise ValidationError("El límite de crédito no puede ser negativo.")
