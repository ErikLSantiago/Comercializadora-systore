from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class AccountPrepaymentApplyWizard(models.TransientModel):
    _name = "account.prepayment.apply.wizard"
    _description = "Apply prepayment account to settle invoice"

    move_id = fields.Many2one("account.move", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="move_id.company_id", store=True, readonly=True)

    date = fields.Date(required=True, default=fields.Date.context_today)
    journal_id = fields.Many2one(
        "account.journal",
        required=True,
        domain="[('company_id', '=', company_id), ('type', 'in', ('general','sale','purchase'))]",
        help="Diario donde se registrará el asiento (recomendado: Misceláneo/General).",
    )
    prepayment_account_id = fields.Many2one(
        "account.account",
        required=True,
        domain="[('company_ids', 'in', company_id), ('account_type', 'in', ('asset_current','asset_non_current','liability_current','liability_non_current','asset_receivable','liability_payable','income_other'))]",
        help="Cuenta de anticipo que se aplicará contra la factura. Puede ser de activo, pasivo, CxC, CxP u otros ingresos.",
    )
    amount = fields.Monetary(required=True)
    currency_id = fields.Many2one(related="move_id.currency_id", readonly=True)
    memo = fields.Char(default="Aplicación de anticipo")

    def _get_open_ar_ap_line(self, move):
        move.ensure_one()
        lines = move.line_ids.filtered(
            lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
            and not l.reconciled
            and l.balance != 0
        )
        if not lines:
            return False
        return lines.sorted(key=lambda l: abs(l.amount_residual), reverse=True)[0]

    def _auto_reconcile_prepayment_line(self, settle_line):
        """Si la cuenta de anticipo es CxC/CxP, intenta conciliarla con apuntes abiertos
        del mismo partner y misma cuenta, empezando por los más antiguos."""
        self.ensure_one()
        account = settle_line.account_id
        if account.account_type not in ("asset_receivable", "liability_payable"):
            return

        candidate_lines = self.env["account.move.line"].search([
            ("account_id", "=", account.id),
            ("partner_id", "=", settle_line.partner_id.id),
            ("reconciled", "=", False),
            ("id", "!=", settle_line.id),
            ("parent_state", "=", "posted"),
            ("company_id", "=", self.company_id.id),
        ], order="date asc, id asc")

        if not candidate_lines:
            return

        lines_to_reconcile = settle_line
        for line in candidate_lines:
            if line.balance == 0:
                continue
            # Debe ser signo opuesto para poder conciliarse
            if line.balance * settle_line.balance < 0:
                lines_to_reconcile += line
                if abs(sum(lines_to_reconcile.mapped("balance"))) < 0.00001:
                    break

        if len(lines_to_reconcile) > 1:
            lines_to_reconcile.reconcile()

    def action_apply(self):
        self.ensure_one()
        move = self.move_id

        if move.state != "posted":
            raise UserError(_("La factura debe estar publicada."))

        open_line = self._get_open_ar_ap_line(move)
        if not open_line:
            raise UserError(_("No se encontró una línea abierta de CxC/CxP para conciliar."))

        if self.amount <= 0:
            raise UserError(_("El monto debe ser mayor a 0."))

        if move.currency_id != move.company_id.currency_id:
            raise UserError(_("Este módulo está pensado para una sola moneda (misma que la compañía)."))

        precision = move.currency_id.decimal_places
        if float_compare(self.amount, abs(move.amount_residual), precision_digits=precision) == 1:
            raise UserError(_("El monto no puede ser mayor al saldo pendiente de la factura."))

        is_payable = open_line.account_id.account_type == "liability_payable"
        amount = self.amount

        if is_payable:
            line_arap = (0, 0, {
                "name": self.memo or _("Aplicación de anticipo"),
                "account_id": open_line.account_id.id,
                "debit": amount,
                "credit": 0.0,
                "partner_id": move.partner_id.id,
            })
            line_prep = (0, 0, {
                "name": self.memo or _("Aplicación de anticipo"),
                "account_id": self.prepayment_account_id.id,
                "debit": 0.0,
                "credit": amount,
                "partner_id": move.partner_id.id,
            })
        else:
            line_arap = (0, 0, {
                "name": self.memo or _("Aplicación de anticipo"),
                "account_id": open_line.account_id.id,
                "debit": 0.0,
                "credit": amount,
                "partner_id": move.partner_id.id,
            })
            line_prep = (0, 0, {
                "name": self.memo or _("Aplicación de anticipo"),
                "account_id": self.prepayment_account_id.id,
                "debit": amount,
                "credit": 0.0,
                "partner_id": move.partner_id.id,
            })

        settle_move = self.env["account.move"].create({
            "move_type": "entry",
            "date": self.date,
            "journal_id": self.journal_id.id,
            "ref": f"{self.memo or 'Aplicación anticipo'} - {move.name}",
            "line_ids": [line_arap, line_prep],
        })
        settle_move.action_post()

        settle_invoice_line = settle_move.line_ids.filtered(
            lambda l: l.account_id.id == open_line.account_id.id and not l.reconciled
        )[:1]
        if not settle_invoice_line:
            raise UserError(_("No se encontró línea conciliable en el asiento generado."))

        (open_line + settle_invoice_line).reconcile()

        settle_prepayment_line = settle_move.line_ids.filtered(
            lambda l: l.account_id.id == self.prepayment_account_id.id and not l.reconciled
        )[:1]
        if settle_prepayment_line:
            self._auto_reconcile_prepayment_line(settle_prepayment_line)

        return {"type": "ir.actions.act_window_close"}
