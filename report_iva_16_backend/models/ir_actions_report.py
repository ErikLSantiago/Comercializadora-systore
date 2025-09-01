
# -*- coding: utf-8 -*-
from odoo import models, _
import re

def _find_insert_index(html):
    html = html or ""
    # 1) Last TABLE mentioning Subtotal/Total
    pat_table = re.compile(r"(<table\b[^>]*>[\s\S]*?(?:Subtotal|Sub\s*total|Total)[\s\S]*?</table>)", re.I)
    m = list(pat_table.finditer(html))
    if m:
        return m[-1].end()

    # 2) Last DIV/SECTION/ARTICLE mentioning Subtotal/Total
    pat_block = re.compile(r"(<(?:div|section|article)\b[^>]*>[\s\S]*?(?:Subtotal|Sub\s*total|Total)[\s\S]*?</(?:div|section|article)>)", re.I)
    m = list(pat_block.finditer(html))
    if m:
        return m[-1].end()

    # 3) Before </body> as last resort
    m = re.search(r"</body\s*>", html, re.I)
    return m.start() if m else len(html)

def _inject_iva_block(html_text, subtotal_str, iva_str, total_display_str):
    try:
        insert_at = _find_insert_index(html_text)
        block = f"""
<div class="iva16-block" style="margin-top:8px; font-size:13px;">
  <p><strong>{_('Resumen (presentación con IVA 16%)')}</strong></p>
  <table class="iva16-table" style="width:100%">
    <tr><td>Subtotal</td><td style="text-align:right;">{subtotal_str}</td></tr>
    <tr><td>IVA (16%)</td><td style="text-align:right;">{iva_str}</td></tr>
    <tr><td><strong>Total</strong></td><td style="text-align:right;"><strong>{total_display_str}</strong></td></tr>
  </table>
  <p style="font-size:11px; color:#666;">{_('Cálculo de presentación en PDF. No impacta impuestos ni asientos contables en Odoo. Total mostrado es el del documento original.')}</p>
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
        total_display = record.currency_id.round(total)
        return subtotal, iva, total_display

    # Odoo 18 signature
    def _render_qweb_html(self, reportname, docids, data=None):
        html_res, qwebhtml_report = super()._render_qweb_html(reportname, docids, data=data)
        try:
            if self.model not in ("sale.order", "purchase.order"):
                return html_res, qwebhtml_report

            records = self.env[self.model].browse(docids).exists()
            # Normalize to list (some engines return a single string for all records)
            html_list = html_res if isinstance(html_res, list) else [html_res]

            new_list = []
            if len(html_list) == len(records) and records:
                for rec, html_doc in zip(records, html_list):
                    subtotal, iva, total_display = self._compute_subtotals(rec)
                    subtotal_str = self._format_currency(rec.currency_id, subtotal, lang=getattr(rec.partner_id, "lang", None))
                    iva_str = self._format_currency(rec.currency_id, iva, lang=getattr(rec.partner_id, "lang", None))
                    total_str = self._format_currency(rec.currency_id, total_display, lang=getattr(rec.partner_id, "lang", None))
                    new_list.append(_inject_iva_block(html_doc, subtotal_str, iva_str, total_str))
            else:
                # Mismatch or unknown mapping: inject once using first record (common case: single doc)
                if records:
                    rec = records[0]
                    subtotal, iva, total_display = self._compute_subtotals(rec)
                    subtotal_str = self._format_currency(rec.currency_id, subtotal, lang=getattr(rec.partner_id, "lang", None))
                    iva_str = self._format_currency(rec.currency_id, iva, lang=getattr(rec.partner_id, "lang", None))
                    total_str = self._format_currency(rec.currency_id, total_display, lang=getattr(rec.partner_id, "lang", None))
                else:
                    subtotal_str = iva_str = total_str = ""
                for html_doc in html_list:
                    new_list.append(_inject_iva_block(html_doc, subtotal_str, iva_str, total_str))

            return new_list if isinstance(html_res, list) else (new_list[0] if new_list else html_res), qwebhtml_report
        except Exception:
            return html_res, qwebhtml_report

    # Odoo 18 signature
    def _render_qweb_pdf(self, reportname, docids, data=None):
        html_res, qwebhtml_report = self._render_qweb_html(reportname, docids, data=data)

        # Ensure list of unicode strings (wkhtmltopdf expects text)
        if isinstance(html_res, list):
            html_docs = [h.decode("utf-8") if isinstance(h, (bytes, bytearray)) else h for h in html_res]
        else:
            html_docs = [html_res.decode("utf-8")] if isinstance(html_res, (bytes, bytearray)) else [html_res]

        res = super()._run_wkhtmltopdf(html_docs, report_ref=self)
        pdf_content = res[0] if isinstance(res, tuple) else res
        return (pdf_content, "pdf")
