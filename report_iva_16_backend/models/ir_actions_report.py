
# -*- coding: utf-8 -*-
from odoo import api, models, _
import re
from markupsafe import Markup

# Robust HTML injector to append IVA block after the last table containing a 'Total' label.
def _inject_iva_block(html_text, subtotal_str, iva_str, total_str):
    try:
        # Find the last table that mentions 'Total' (case-insensitive, with accents/tags)
        pattern = re.compile(r"(<table\b[^>]*>.*?Total.*?</table>)", re.I | re.S)
        matches = list(pattern.finditer(html_text))
        if matches:
            last = matches[-1]
            insert_at = last.end()
        else:
            # fallback: before </body>
            mbody = re.search(r"</body\s*>", html_text, re.I)
            insert_at = mbody.start() if mbody else len(html_text)

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
        return html_text[:insert_at] + block + html_text[insert_at:]
    except Exception:
        return html_text

class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _format_currency(self, currency, amount, lang=None):
        # Use Odoo's format_amount helper when available via qwebcontext; otherwise basic fallback
        # Here we use currency's rounding and symbol placement.
        amount = currency.round(amount)
        # Build with symbol
        symbol = currency.symbol or ''
        if currency.position == 'after':
            return f"{amount:,.2f} {symbol}"
        else:
            return f"{symbol} {amount:,.2f}"

    def _compute_subtotals(self, record):
        # subtotal = total / 1.16 ; iva = subtotal * 0.16
        rate = 0.16
        total = record.amount_total or 0.0
        subtotal = record.currency_id.round(total / (1.0 + rate))
        iva = record.currency_id.round(subtotal * rate)
        total_calc = subtotal + iva
        return subtotal, iva, total_calc

    def _render_qweb_html(self, docids, data=None):
        html_res, qwebhtml_report = super()._render_qweb_html(docids, data=data)
        try:
            # Only target the standard Sale and Purchase reports by report_name
            target_reports = ('sale.report_saleorder', 'purchase.report_purchaseorder')
            if self.report_name not in target_reports:
                return html_res, qwebhtml_report

            # Determine model
            model = 'sale.order' if self.report_name == 'sale.report_saleorder' else 'purchase.order'
            records = self.env[model].browse(docids).exists()

            # Ensure html_res is a list of HTML documents aligned with records
            html_list = html_res if isinstance(html_res, list) else [html_res]
            # If mismatch, just return untouched
            if not records or len(html_list) != len(records):
                return html_res, qwebhtml_report

            # Inject block per document
            new_list = []
            for rec, html_doc in zip(records, html_list):
                subtotal, iva, total_calc = self._compute_subtotals(rec)
                subtotal_str = self._format_currency(rec.currency_id, subtotal, lang=rec.partner_id.lang)
                iva_str = self._format_currency(rec.currency_id, iva, lang=rec.partner_id.lang)
                total_str = self._format_currency(rec.currency_id, total_calc, lang=rec.partner_id.lang)
                new_list.append(_inject_iva_block(html_doc, subtotal_str, iva_str, total_str))

            return new_list, qwebhtml_report
        except Exception:
            # Never block report rendering
            return html_res, qwebhtml_report

    # Also override _render_qweb_pdf to be safe in some flows that skip HTML stage
    def _render_qweb_pdf(self, docids, data=None):
        # Render HTML first to inject our block
        html_res, qwebhtml_report = self._render_qweb_html(docids, data=data)
        if isinstance(html_res, list):
            html_combined = b"".join([h.encode('utf-8') if isinstance(h, str) else h for h in html_res])
        else:
            html_combined = html_res.encode('utf-8') if isinstance(html_res, str) else html_res
        # Use Odoo converter to PDF
        pdf_content, _ = super()._run_wkhtmltopdf([html_combined], report_ref=self)
        return (pdf_content, 'pdf')
