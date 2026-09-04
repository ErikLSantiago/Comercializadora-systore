# -*- coding: utf-8 -*-
import base64
import csv
import io

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class MarketplaceSettlementImportCSV(models.TransientModel):
    _name = "marketplace.settlement.import.csv"
    _description = "Import Settlement CSV"

    settlement_id = fields.Many2one("marketplace.settlement", required=True)
    csv_file = fields.Binary(string="CSV File", required=True)
    filename = fields.Char()

    def _get_account_by_code(self, code):
        if not code:
            return False
        code = str(code).strip()
        Account = self.env["account.account"]
        company = self.settlement_id.company_id

        # Odoo 17/18: account.account can be multi-company via `company_ids` (M2M)
        # and may not have `company_id` anymore. Keep backward compatibility.
        domain = [("code", "=", code)]
        if "company_id" in Account._fields:
            domain.append(("company_id", "=", company.id))
        elif "company_ids" in Account._fields:
            domain.append(("company_ids", "in", company.id))

        acc = Account.search(domain, limit=1)
        if not acc:
            raise UserError(_("Account with code '%s' not found in company '%s'.") % (code, self.settlement_id.company_id.display_name))
        return acc

    def _find_sale_order(self, order_ref):
        so = self.env["sale.order"].search([
            ("name", "=", order_ref),
            ("company_id", "=", self.settlement_id.company_id.id),
        ], limit=1)
        return so

    def _find_invoice(self, so, order_ref):
        Move = self.env["account.move"]
        inv = False
        if so:
            # Prefer posted customer invoices linked to SO
            candidates = so.invoice_ids.filtered(lambda m: m.state == "posted" and m.move_type == "out_invoice")
            if candidates:
                inv = candidates[0]
        if not inv:
            # Fallback: match by invoice origin
            inv = Move.search([
                ("invoice_origin", "=", order_ref),
                ("company_id", "=", self.settlement_id.company_id.id),
                ("state", "=", "posted"),
                ("move_type", "=", "out_invoice"),
            ], limit=1)
        return inv

    def action_import(self):
        self.ensure_one()
        if not self.csv_file:
            raise UserError(_("Please upload a CSV file."))

        raw = base64.b64decode(self.csv_file)
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")

        f = io.StringIO(text)
        reader = csv.DictReader(f)
        required = {
            "order_ref",
            "withheld_vat_amount", "withheld_vat_account_code",
            "shipping_amount", "shipping_account_code",
            "seller_commission_amount", "seller_commission_account_code",
        }
        missing = required - set([h.strip() for h in (reader.fieldnames or [])])
        if missing:
            raise UserError(_("CSV missing required columns: %s") % ", ".join(sorted(missing)))

        lines_cmds = [(5, 0, 0)]
        for row in reader:
            order_ref = (row.get("order_ref") or "").strip()
            if not order_ref:
                continue

            def _to_float(v):
                v = (v or "").strip()
                if not v:
                    return 0.0
                # allow commas
                v = v.replace(",", "")
                return float(v)

            so = self._find_sale_order(order_ref)
            inv = self._find_invoice(so, order_ref)

            withheld_amt = _to_float(row.get("withheld_vat_amount"))
            ship_amt = _to_float(row.get("shipping_amount"))
            comm_amt = _to_float(row.get("seller_commission_amount"))

            withheld_acc = self._get_account_by_code(row.get("withheld_vat_account_code")) if withheld_amt else False
            ship_acc = self._get_account_by_code(row.get("shipping_account_code")) if ship_amt else False
            comm_acc = self._get_account_by_code(row.get("seller_commission_account_code")) if comm_amt else False

            gross = inv.amount_total if inv else (so.amount_total if so else 0.0)

            lines_cmds.append((0, 0, {
                "order_ref": order_ref,
                "sale_order_id": so.id if so else False,
                "invoice_id": inv.id if inv else False,
                "amount_gross": gross,
                "withheld_vat_amount": withheld_amt,
                "withheld_vat_account_id": withheld_acc.id if withheld_acc else False,
                "shipping_amount": ship_amt,
                "shipping_account_id": ship_acc.id if ship_acc else False,
                "seller_commission_amount": comm_amt,
                "seller_commission_account_id": comm_acc.id if comm_acc else False,
            }))

        if len(lines_cmds) <= 1:
            raise UserError(_("No valid rows found in CSV."))

        self.settlement_id.write({"line_ids": lines_cmds, "state": "imported"})
        return self.settlement_id.action_open_form()
