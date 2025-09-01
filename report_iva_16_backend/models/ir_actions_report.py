
# -*- coding: utf-8 -*-
from odoo import models, _
import re

def _inject_iva_block(html_text, subtotal_str, iva_str, total_str):
    try:
        pattern = re.compile(r"(<table\b[^>]*>.*?Total.*?</table>)", re.I | re.S)
        matches = list(pattern.finditer(html_text or ""))
        if matches:
            insert_at = matches[-1].end()
        else:
            mbody = re.search(r"</body\s*>", html_text or "", re.I)
            insert_at = mbody.start() if mbody else len(html_text or "")
        block = f"""
<div class="iva16-block" style="margin-top:8px; font-size:13px;">
  <style>
    @media screen {{ .iva16-block {{ display:none; }} }}
    @media print  {{ .iva16-block {{ display:block; }} }}
    .iva16-table td {{ padding:2px 0; }}
    .iva16-note {{ font-size:11px; color:#666; }}
  </style>
  <p><strong>{_('Resumen (presentación con IVA 16%)')}</strong></p>
  <table class="iva16-table" style="width:100%">
    <tr><td>Subtotal</td><td style="text-align:right;">{subtotal_str}</td></tr>
    <tr><td>IVA (16%)</td><td style="text-align:right;">{iva_str}</td></tr>
    <tr><td><strong>Total</strong></td><td style="text-align:right;"><strong>{total_str}</strong></td></tr>
  </table>
  <p class="iva16-note">{_('Cálculo visible solo en impresión/PDF. No impacta impuestos ni asientos contables en Odoo.')}</p>
</div>
"""
        return (html_text or "")[:insert_at] + block + (html_text or "")[insert_at:]
    except Exception:
        return html_text

class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _format_currency(self, currency, amount, lang=None):
        amount = currency.round(amount or 0.0)
        symbol = currency.symbol or ""
        if currency.position == "after":
            return f"{amount:,.2f} {symbol}"
        return f"{symbol} {amount:,.2f}"

    def _compute_subtotals(self, record):
        rate = 0.16
        total = record.amount_total or 0.0
        subtotal = record.currency_id.round(total / (1.0 + rate))
        iva = record.currency_id.round(subtotal * rate)
        total_calc = subtotal + iva
        return subtotal, iva, total_calc

    def _render_qweb_html(self, docids, data=None):
        html_res, qwebhtml_report = super()._render_qweb_html(docids, data=data)
        try:
            if self.model not in ("sale.order", "purchase.order"):
                return html_res, qwebhtml_report

            records = self.env[self.model].browse(docids).exists()
            html_list = html_res if isinstance(html_res, list) else [html_res]
            if not records or len(html_list) != len(records):
                return html_res, qwebhtml_report

            new_list = []
            for rec, html_doc in zip(records, html_list):
                subtotal, iva, total_calc = self._compute_subtotals(rec)
                subtotal_str = self._format_currency(rec.currency_id, subtotal, lang=getattr(rec.partner_id, "lang", None))
                iva_str = self._format_currency(rec.currency_id, iva, lang=getattr(rec.partner_id, "lang", None))
                total_str = self._format_currency(rec.currency_id, total_calc, lang=getattr(rec.partner_id, "lang", None))
                new_list.append(_inject_iva_block(html_doc, subtotal_str, iva_str, total_str))

            return new_list, qwebhtml_report
        except Exception:
            return html_res, qwebhtml_report

    # Odoo 18 signature: _render_qweb_pdf(self, reportname, docids, data=None)
    def _render_qweb_pdf(self, reportname, docids, data=None):
        # Render HTML first (this also injects our block)
        html_res, qwebhtml_report = self._render_qweb_html(docids, data=data)

        # Normalize to list of HTML bytes
        if isinstance(html_res, list):
            html_docs = [h.encode("utf-8") if isinstance(h, str) else h for h in html_res]
        else:
            html_docs = [(html_res.encode("utf-8") if isinstance(html_res, str) else html_res)]

        # Convert to PDF using Odoo helper
        pdf_content, _ = super()._run_wkhtmltopdf(html_docs, report_ref=self)
        return (pdf_content, "pdf")
