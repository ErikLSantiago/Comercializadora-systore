from odoo import fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_open_prepayment_apply_wizard(self):
        self.ensure_one()
        if self.state != "posted":
            raise UserError(_("La factura debe estar publicada (posted)."))
        if self.move_type not in ("in_invoice", "in_refund", "out_invoice", "out_refund"):
            raise UserError(_("Esta acción solo aplica para facturas/NC de cliente o proveedor."))
        if self.payment_state == "paid":
            raise UserError(_("Esta factura ya está pagada."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Pagar con anticipo"),
            "res_model": "account.prepayment.apply.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_move_id": self.id,
                "default_date": fields.Date.context_today(self),
                "default_amount": abs(self.amount_residual),
            },
        }
