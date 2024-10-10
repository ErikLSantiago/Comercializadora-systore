# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models,api, _
from odoo.exceptions import UserError, Warning, ValidationError


class account_payment(models.TransientModel):
    _inherit = 'account.payment.register'

    manual_currency_rate_active = fields.Boolean('Apply Manual Exchange')
    manual_currency_rate = fields.Float('Rate', digits=(12, 6))

    @api.model
    def default_get(self, default_fields):
        rec = super(account_payment, self).default_get(default_fields)
        active_ids = self._context.get('active_ids') or self._context.get('active_id')
        active_model = self._context.get('active_model')

        # Check for selected invoices ids
        if not active_ids or active_model != 'account.move':
            return rec
        invoices = self.env['account.move'].browse(active_ids).filtered(
            lambda move: move.is_invoice(include_receipts=True))
        if len(invoices or []) > 1:
            if all(inv.manual_currency_rate_active == False for inv in invoices):
                return rec;
            if any(inv.manual_currency_rate_active == False for inv in invoices):
                raise ValidationError(_("Selected invoice to make payment have not similer currency or currency rate is not same.\n Make sure selected invoices have same currency and same manual currency rate."));
            else:
                rate = invoices[0].manual_currency_rate
                if any(inv.manual_currency_rate != rate for inv in invoices):
                    raise ValidationError(_("Selected invoice to make payment have not similer currency or currency rate is not same.\n Make sure selected invoices have same currency and same manual currency rate."));
        rec.update({
            'manual_currency_rate_active': invoices[0].manual_currency_rate_active,
            'manual_currency_rate': invoices[0].manual_currency_rate
        })
        return rec

    @api.onchange('manual_currency_rate_active')
    def _onchange_manual_currency_rate_active(self):
        for wizard in self:
            active_ids = self._context.get('active_ids') or self._context.get('active_id')
            active_model = self._context.get('active_model')
            invoices = self.env['account.move'].browse(active_ids).filtered(
            lambda move: move.is_invoice(include_receipts=True))
            if active_model =="account.move" and len(invoices) > 1:
                if any(inv.manual_currency_rate_active and inv.currency_id.id == inv.company_id.currency_id.id for inv in invoices):
                    raise UserError(_('Company currency and invoice currency same for one or more selected invoices, You can not add manual Exchange rate for same currency.'));
            else:
                if wizard.manual_currency_rate_active and wizard.currency_id == wizard.company_currency_id:
                    wizard.manual_currency_rate_active = False
                    raise UserError(_('Company currency and invoice currency same, You can not add manual Exchange rate for same currency.'))



    @api.depends('source_amount', 'source_amount_currency', 'source_currency_id', 'company_id', 'currency_id', 'payment_date', 'manual_currency_rate')
    def _compute_amount(self):
        for wizard in self:
            if wizard.source_currency_id == wizard.currency_id:
                # Same currency.
                wizard.amount = wizard.source_amount_currency
            elif wizard.currency_id == wizard.company_id.currency_id:
                # Payment expressed on the company's currency.
                wizard.amount = wizard.source_amount
            else:
                # Foreign currency on payment different than the one set on the journal entries.
                if self.manual_currency_rate_active and self.manual_currency_rate > 0:
                    currency_rate = self.manual_currency_rate
                    amount_payment_currency = wizard.source_amount * currency_rate
                else:
                    amount_payment_currency = wizard.company_id.currency_id._convert(wizard.source_amount, wizard.currency_id, wizard.company_id, wizard.payment_date)
                wizard.amount = amount_payment_currency

    @api.depends('amount')
    def _compute_payment_difference(self):
        for wizard in self:
            if wizard.source_currency_id == wizard.currency_id:
                # Same currency.
                wizard.payment_difference = wizard.source_amount_currency - wizard.amount
            elif wizard.currency_id == wizard.company_id.currency_id:
                # Payment expressed on the company's currency.
                wizard.payment_difference = wizard.source_amount - wizard.amount
            else:
                # Foreign currency on payment different than the one set on the journal entries.
                if self.manual_currency_rate_active and self.manual_currency_rate > 0:
                    currency_rate = self.manual_currency_rate
                    amount_payment_currency = wizard.source_amount * currency_rate
                else:
                    amount_payment_currency = wizard.company_id.currency_id._convert(wizard.source_amount, wizard.currency_id, wizard.company_id, wizard.payment_date)
                wizard.payment_difference = amount_payment_currency - wizard.amount


    def _create_payment_vals_from_wizard(self):
        res = super(account_payment, self)._create_payment_vals_from_wizard()
        if self.manual_currency_rate_active:
            res.update({'manual_currency_rate_active': self.manual_currency_rate_active, 'manual_currency_rate': self.manual_currency_rate})
        return res




class AccountPayment(models.Model):
    _inherit = "account.payment"
    _description = "Payments"

    manual_currency_rate_active = fields.Boolean('Apply Manual Exchange')
    manual_currency_rate = fields.Float('Rate', digits=(12, 6))
    amount_currency = fields.Float('Amount Currency')
    check_active_currency = fields.Boolean('Check Active Currency')

    @api.onchange('manual_currency_rate_active', 'currency_id')
    def check_currency_id(self):
        for payment in self:
            if payment.manual_currency_rate_active:
                if payment.currency_id == payment.company_id.currency_id:
                    payment.manual_currency_rate_active = False
                    raise UserError(_('Company currency and Payment currency same, You can not add manual Exchange rate for same currency.'))

    @api.model
    def default_get(self, default_fields):
        rec = super(AccountPayment, self).default_get(default_fields)
        active_ids = self._context.get('active_ids') or self._context.get('active_id')
        active_model = self._context.get('active_model')

        # Check for selected invoices ids
        if not active_ids or active_model != 'account.move':
            return rec
        invoices = self.env['account.move'].browse(active_ids).filtered(
            lambda move: move.is_invoice(include_receipts=True))
        rec.update({
            'manual_currency_rate_active': invoices[0].manual_currency_rate_active,
            'manual_currency_rate': invoices[0].manual_currency_rate
        })
        return rec


    @api.model
    def _compute_payment_amount(self, invoices, currency, journal, date):
        '''Compute the total amount for the payment wizard.
        :param invoices:    Invoices on which compute the total as an account.invoice recordset.
        :param currency:    The payment's currency as a res.currency record.
        :param journal:     The payment's journal as an account.journal record.
        :param date:        The payment's date as a datetime.date object.
        :return:            The total amount to pay the invoices.
        '''
        company = journal.company_id
        currency = currency or journal.currency_id or company.currency_id
        date = date or fields.Date.today()

        if not invoices:
            return 0.0

        self.env['account.move'].flush(['type', 'currency_id'])
        self.env['account.move.line'].flush(['amount_residual', 'amount_residual_currency', 'move_id', 'account_id'])
        self.env['account.account'].flush(['user_type_id'])
        self.env['account.account.type'].flush(['type'])
        self._cr.execute('''
                SELECT
                    move.type AS type,
                    move.currency_id AS currency_id,
                    SUM(line.amount_residual) AS amount_residual,
                    SUM(line.amount_residual_currency) AS residual_currency
                FROM account_move move
                LEFT JOIN account_move_line line ON line.move_id = move.id
                LEFT JOIN account_account account ON account.id = line.account_id
                LEFT JOIN account_account_type account_type ON account_type.id = account.user_type_id
                WHERE move.id IN %s
                AND account_type.type IN ('receivable', 'payable')
                GROUP BY move.id, move.type
            ''', [tuple(invoices.ids)])
        query_res = self._cr.dictfetchall()

        total = 0.0
        for inv in invoices:
            for res in query_res:
                move_currency = self.env['res.currency'].browse(res['currency_id'])
                if move_currency == currency and move_currency != company.currency_id:
                    total += res['residual_currency']
                else:
                    if not inv.manual_currency_rate_active:
                        total += company.currency_id._convert(res['amount_residual'], currency, company, date)
                    else:
                        total += res['residual_currency'] * inv.manual_currency_rate
        return total


    @api.depends('invoice_ids', 'amount', 'payment_date', 'currency_id', 'payment_type', 'manual_currency_rate')
    def _compute_payment_difference(self):
        draft_payments = self.filtered(lambda p: p.invoice_ids and p.state == 'draft')
        for pay in draft_payments:
            payment_amount = -pay.amount if pay.payment_type == 'outbound' else pay.amount
            pay.payment_difference = pay._compute_payment_amount(pay.invoice_ids, pay.currency_id, pay.journal_id,
                                                                 pay.payment_date) - payment_amount
        (self - draft_payments).payment_difference = 0

    def _prepare_move_line_default_vals(self, write_off_line_vals=None):
        ''' Prepare the dictionary to create the default account.move.lines for the current payment.
        :param write_off_line_vals: Optional dictionary to create a write-off account.move.line easily containing:
            * amount:       The amount to be added to the counterpart amount.
            * name:         The label to set on the line.
            * account_id:   The account on which create the write-off.
        :return: A list of python dictionary to be passed to the account.move.line's 'create' method.
        '''
        self.ensure_one()
        write_off_line_vals = write_off_line_vals or {}

        if not self.outstanding_account_id:
            raise UserError(_(
                "You can't create a new payment without an outstanding payments/receipts account set either on the company or the %s payment method in the %s journal.",
                self.payment_method_line_id.name, self.journal_id.display_name))

        # Compute amounts.
        write_off_amount_currency = write_off_line_vals.get('amount', 0.0)

        if self.payment_type == 'inbound':
            # Receive money.
            liquidity_amount_currency = self.amount
        elif self.payment_type == 'outbound':
            # Send money.
            liquidity_amount_currency = -self.amount
            write_off_amount_currency *= -1
        else:
            liquidity_amount_currency = write_off_amount_currency = 0.0


        if self.manual_currency_rate_active and self.manual_currency_rate > 0:
            currency_rate = self.company_id.currency_id.rate / self.manual_currency_rate
            liquidity_balance = liquidity_amount_currency * currency_rate            
            counterpart_amount_currency = -liquidity_amount_currency - write_off_amount_currency            
            write_off_balance = write_off_amount_currency * currency_rate
            counterpart_balance = -liquidity_balance - write_off_balance
            currency_id = self.currency_id.id
        
        else:

            write_off_balance = self.currency_id._convert(
                write_off_amount_currency,
                self.company_id.currency_id,
                self.company_id,
                self.date,
            )
            liquidity_balance = self.currency_id._convert(
                liquidity_amount_currency,
                self.company_id.currency_id,
                self.company_id,
                self.date,
            )
            counterpart_amount_currency = -liquidity_amount_currency - write_off_amount_currency
            counterpart_balance = -liquidity_balance - write_off_balance
            currency_id = self.currency_id.id


        if self.is_internal_transfer:
            if self.payment_type == 'inbound':
                liquidity_line_name = _('Transfer to %s', self.journal_id.name)
            else: # payment.payment_type == 'outbound':
                liquidity_line_name = _('Transfer from %s', self.journal_id.name)
        else:
            liquidity_line_name = self.payment_reference

        # Compute a default label to set on the journal items.

        payment_display_name = {
            'outbound-customer': _("Customer Reimbursement"),
            'inbound-customer': _("Customer Payment"),
            'outbound-supplier': _("Vendor Payment"),
            'inbound-supplier': _("Vendor Reimbursement"),
        }

        default_line_name = self.env['account.move.line']._get_default_line_name(
            _("Internal Transfer") if self.is_internal_transfer else payment_display_name['%s-%s' % (self.payment_type, self.partner_type)],
            self.amount,
            self.currency_id,
            self.date,
            partner=self.partner_id,
        )

        line_vals_list = [
            # Liquidity line.
            {
                'name': liquidity_line_name or default_line_name,
                'date_maturity': self.date,
                'amount_currency': liquidity_amount_currency,
                'currency_id': currency_id,
                'debit': liquidity_balance if liquidity_balance > 0.0 else 0.0,
                'credit': -liquidity_balance if liquidity_balance < 0.0 else 0.0,
                'partner_id': self.partner_id.id,
                'account_id': self.outstanding_account_id.id,
            },
            # Receivable / Payable.
            {
                'name': self.payment_reference or default_line_name,
                'date_maturity': self.date,
                'amount_currency': counterpart_amount_currency,
                'currency_id': currency_id,
                'debit': counterpart_balance if counterpart_balance > 0.0 else 0.0,
                'credit': -counterpart_balance if counterpart_balance < 0.0 else 0.0,
                'partner_id': self.partner_id.id,
                'account_id': self.destination_account_id.id,
            },
        ]
        if not self.currency_id.is_zero(write_off_amount_currency):
            # Write-off line.
            line_vals_list.append({
                'name': write_off_line_vals.get('name') or default_line_name,
                'amount_currency': write_off_amount_currency,
                'currency_id': currency_id,
                'debit': write_off_balance if write_off_balance > 0.0 else 0.0,
                'credit': -write_off_balance if write_off_balance < 0.0 else 0.0,
                'partner_id': self.partner_id.id,
                'account_id': write_off_line_vals.get('account_id'),
            })
        return line_vals_list

    def write(self,vals):
        result = super().write(vals)
        if vals.get('amount') and vals.get('amount_currency'):
            for record in self:
                record.amount_currency = vals.get('amount')
        return result
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('amount_currency'):
                vals.update({'amount':vals.get('amount_currency')})
            result = super().create(vals)
            if vals.get('amount'):
                vals.update({'amount_currency':vals.get('amount')})
                result.sync_amount()
        return result

    @api.onchange('amount_currency')
    def onchange_amount_currency(self):
        for record in self:
            record.amount = record.amount_currency

    def action_post(self):
        ''' draft -> posted '''
        self.ensure_one()
        if self.check_active_currency == False : 
            self.move_id.update({'manual_currency_rate_active': self.manual_currency_rate_active,
                'manual_currency_rate':self.manual_currency_rate,})
            self.update({'amount':self.amount_currency})
        self.move_id._post(soft=False)

        self.filtered(
            lambda pay: pay.is_internal_transfer and not pay.paired_internal_transfer_payment_id
        )._create_paired_internal_transfer_payment()

    def action_draft(self):
        ''' posted -> draft '''
        if self.check_active_currency == False : 
           self.update({'amount':self.amount_currency})
        self.move_id.button_draft()


    def sync_amount(self):
        for record in self:
            if record.manual_currency_rate_active and record.manual_currency_rate:
                if record.company_id.currency_id.id == record.currency_id.id:
                    if self.check_active_currency == True : 
                       record.amount_currency = record.amount 
                else:
                    record.amount_currency = record.amount
            else:
                record.amount_currency = record.amount


        # ''' Prepare the dictionary to create the default account.move.lines for the current payment.
        # :param write_off_line_vals: Optional dictionary to create a write-off account.move.line easily containing:
        #     * amount:       The amount to be added to the counterpart amount.
        #     * name:         The label to set on the line.
        #     * account_id:   The account on which create the write-off.
        # :return: A list of python dictionary to be passed to the account.move.line's 'create' method.
        # '''
        # self.ensure_one()
        # write_off_line_vals = write_off_line_vals or {}

        # if not self.outstanding_account_id:
        #     raise UserError(_(
        #         "You can't create a new payment without an outstanding payments/receipts account set either on the company or the %s payment method in the %s journal.",
        #         self.payment_method_line_id.name, self.journal_id.display_name))

        # # Compute amounts.
        # write_off_amount_currency = write_off_line_vals.get('amount', 0.0)

        # if self.payment_type == 'inbound':
        #     # Receive money.
        #     liquidity_amount_currency = self.amount
        # elif self.payment_type == 'outbound':
        #     # Send money.
        #     liquidity_amount_currency = -self.amount
        #     write_off_amount_currency *= -1
        # else:
        #     liquidity_amount_currency = write_off_amount_currency = 0.0


        # if self.manual_currency_rate_active and self.manual_currency_rate > 0:
        #     currency_rate = self.company_id.currency_id.rate / self.manual_currency_rate
        #     liquidity_balance = liquidity_amount_currency * currency_rate            
        #     counterpart_amount_currency = -liquidity_amount_currency - write_off_amount_currency            
        #     write_off_balance = write_off_amount_currency * currency_rate
        #     counterpart_balance = -liquidity_balance - write_off_balance
        #     currency_id = self.currency_id.id
        
        # else:

        #     write_off_balance = self.currency_id._convert(
        #         write_off_amount_currency,
        #         self.company_id.currency_id,
        #         self.company_id,
        #         self.date,
        #     )
        #     liquidity_balance = self.currency_id._convert(
        #         liquidity_amount_currency,
        #         self.company_id.currency_id,
        #         self.company_id,
        #         self.date,
        #     )
        #     counterpart_amount_currency = -liquidity_amount_currency - write_off_amount_currency
        #     counterpart_balance = -liquidity_balance - write_off_balance
        #     currency_id = self.currency_id.id


        # if self.is_internal_transfer:
        #     if self.payment_type == 'inbound':
        #         liquidity_line_name = _('Transfer to %s', self.journal_id.name)
        #     else: # payment.payment_type == 'outbound':
        #         liquidity_line_name = _('Transfer from %s', self.journal_id.name)
        # else:
        #     liquidity_line_name = self.payment_reference

        # # Compute a default label to set on the journal items.

        # payment_display_name = {
        #     'outbound-customer': _("Customer Reimbursement"),
        #     'inbound-customer': _("Customer Payment"),
        #     'outbound-supplier': _("Vendor Payment"),
        #     'inbound-supplier': _("Vendor Reimbursement"),
        # }

        # default_line_name = self.env['account.move.line']._get_default_line_name(
        #     _("Internal Transfer") if self.is_internal_transfer else payment_display_name['%s-%s' % (self.payment_type, self.partner_type)],
        #     self.amount,
        #     self.currency_id,
        #     self.date,
        #     partner=self.partner_id,
        # )

        # line_vals_list = [
        #     # Liquidity line.
        #     {
        #         'name': liquidity_line_name or default_line_name,
        #         'date_maturity': self.date,
        #         'amount_currency': liquidity_amount_currency,
        #         'currency_id': currency_id,
        #         'debit': liquidity_balance if liquidity_balance > 0.0 else 0.0,
        #         'credit': -liquidity_balance if liquidity_balance < 0.0 else 0.0,
        #         'partner_id': self.partner_id.id,
        #         'account_id': self.outstanding_account_id.id,
        #     },
        #     # Receivable / Payable.
        #     {
        #         'name': self.payment_reference or default_line_name,
        #         'date_maturity': self.date,
        #         'amount_currency': counterpart_amount_currency,
        #         'currency_id': currency_id,
        #         'debit': counterpart_balance if counterpart_balance > 0.0 else 0.0,
        #         'credit': -counterpart_balance if counterpart_balance < 0.0 else 0.0,
        #         'partner_id': self.partner_id.id,
        #         'account_id': self.destination_account_id.id,
        #     },
        # ]
        # if not self.currency_id.is_zero(write_off_amount_currency):
        #     # Write-off line.
        #     line_vals_list.append({
        #         'name': write_off_line_vals.get('name') or default_line_name,
        #         'amount_currency': write_off_amount_currency,
        #         'currency_id': currency_id,
        #         'debit': write_off_balance if write_off_balance > 0.0 else 0.0,
        #         'credit': -write_off_balance if write_off_balance < 0.0 else 0.0,
        #         'partner_id': self.partner_id.id,
        #         'account_id': write_off_line_vals.get('account_id'),
        #     })
        # return line_vals_list


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
