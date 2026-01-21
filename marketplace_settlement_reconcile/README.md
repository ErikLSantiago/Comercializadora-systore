# Marketplace Settlement Reconcile (CSV) - Odoo 18

## What it does (MVP)
- Create a "Marketplace Settlement" linked to a Bank Statement Line (net deposit).
- Import a CSV with per-order fees and target expense accounts (by account code).
- Post a single journal entry that:
  - Credits receivable per invoice by gross
  - Debits clearing by net
  - Debits expense/withholding accounts by fees
- Reconciles invoices automatically.
- Leaves bank reconciliation to the standard widget: match the bank statement line with clearing account lines from the posted entry.

## Setup
1) Accounting > Configuration > Settings:
   - Set **Marketplace Clearing Account**
   - Set **Marketplace Settlement Journal** (type: General)

## Usage
1) Go to Accounting > Bank > Bank Statements (or Bank Reconciliation) and open the statement line.
2) Click **Marketplace Settlement** button.
3) In the Settlement, click **Import CSV**, upload file.
4) Review totals and click **Post & Reconcile**.
5) In Bank Reconciliation, match the statement line against the clearing account move line(s).

## CSV columns (required)
- order_ref
- withheld_vat_amount
- withheld_vat_account_code
- shipping_amount
- shipping_account_code
- seller_commission_amount
- seller_commission_account_code

Amounts should be numeric. Account codes must exist in Odoo for the company.
