# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class MkpAccountGatewayCommissionLine(models.Model):
    _name = 'mkp.account.gateway.commission.line'
    _description = 'Comisión de pasarela aplicada a factura'
    _order = 'id'
    _check_company_auto = True

    move_id = fields.Many2one(
        'account.move', string='Factura', required=True,
        ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(
        related='move_id.company_id', store=True, precompute=True,
    )
    currency_id = fields.Many2one(
        related='move_id.currency_id', store=True, precompute=True,
    )
    sale_payment_line_id = fields.Many2one(
        'mkp.sale.gateway.payment', string='Pago de la orden',
        ondelete='set null', index=True,
    )
    gateway_config_id = fields.Many2one(
        'mkp.payment.gateway.config', string='Pasarela', required=True,
        check_company=True, ondelete='restrict',
    )
    gateway_partner_id = fields.Many2one(
        related='gateway_config_id.partner_id', string='Contacto',
    )
    payment_amount = fields.Monetary(
        string='Importe procesado', currency_field='currency_id', readonly=True,
    )
    commission_amount = fields.Monetary(
        string='Comisión Pasarela', currency_field='currency_id', readonly=True,
    )
    fixed_commission_amount = fields.Monetary(
        string='Comisión Fija', currency_field='currency_id', readonly=True,
    )
    commission_vat_amount = fields.Monetary(
        string='IVA Comisión Pasarela', currency_field='currency_id', readonly=True,
    )
    fixed_commission_vat_amount = fields.Monetary(
        string='IVA Comisión Fija', currency_field='currency_id', readonly=True,
    )
    total_commission_amount = fields.Monetary(
        string='Comisión total', currency_field='currency_id',
        compute='_compute_total_commission_amount',
    )

    @api.depends(
        'commission_amount', 'fixed_commission_amount',
        'commission_vat_amount', 'fixed_commission_vat_amount',
    )
    def _compute_total_commission_amount(self):
        for line in self:
            line.total_commission_amount = (
                line.commission_amount
                + line.fixed_commission_amount
                + line.commission_vat_amount
                + line.fixed_commission_vat_amount
            )


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Compatibilidad con la versión que admitía una sola pasarela.
    mkp_payment_gateway_config_id = fields.Many2one(
        'mkp.payment.gateway.config', string='Pasarela anterior',
        copy=False, readonly=True, check_company=True,
    )
    mkp_gateway_commission_line_ids = fields.One2many(
        'mkp.account.gateway.commission.line', 'move_id',
        string='Comisiones de pasarelas', copy=False, readonly=True,
    )
    mkp_gateway_commission_amount = fields.Monetary(
        string='Comisión Pasarela aplicada', currency_field='currency_id',
        copy=False, readonly=True,
    )
    mkp_gateway_fixed_commission_amount = fields.Monetary(
        string='Comisión Fija aplicada', currency_field='currency_id',
        copy=False, readonly=True,
    )
    mkp_gateway_commission_vat_amount = fields.Monetary(
        string='IVA Comisión Pasarela aplicado', currency_field='currency_id',
        copy=False, readonly=True,
    )
    mkp_gateway_fixed_commission_vat_amount = fields.Monetary(
        string='IVA Comisión Fija aplicado', currency_field='currency_id',
        copy=False, readonly=True,
    )
    mkp_gateway_total_commission_amount = fields.Monetary(
        string='Comisión total aplicada', currency_field='currency_id',
        compute='_compute_mkp_gateway_total_commission_amount',
    )
    mkp_gateway_commission_move_id = fields.Many2one(
        'account.move', string='Primer asiento de comisiones',
        copy=False, readonly=True, ondelete='restrict',
    )
    mkp_gateway_commission_move_ids = fields.Many2many(
        'account.move', 'account_move_mkp_gateway_commission_rel',
        'invoice_id', 'commission_move_id',
        string='Asientos de comisiones', copy=False, readonly=True,
    )

    @api.depends(
        'mkp_gateway_commission_amount',
        'mkp_gateway_fixed_commission_amount',
        'mkp_gateway_commission_vat_amount',
        'mkp_gateway_fixed_commission_vat_amount',
    )
    def _compute_mkp_gateway_total_commission_amount(self):
        for move in self:
            move.mkp_gateway_total_commission_amount = (
                move.mkp_gateway_commission_amount
                + move.mkp_gateway_fixed_commission_amount
                + move.mkp_gateway_commission_vat_amount
                + move.mkp_gateway_fixed_commission_vat_amount
            )

    def action_post(self):
        res = super().action_post()
        for move in self:
            move._mkp_create_gateway_commission_partial_payment()
        return res

    def _mkp_create_gateway_commission_partial_payment(self):
        self.ensure_one()
        if self.move_type != 'out_invoice' or self.state != 'posted':
            return
        if self.mkp_gateway_commission_move_ids or self.mkp_gateway_commission_move_id:
            return

        sale_orders = self.invoice_line_ids.sale_line_ids.order_id.filtered(
            lambda order: order.company_id == self.company_id
        )
        sale_payment_lines = sale_orders.mkp_gateway_payment_line_ids
        if not sale_payment_lines:
            return

        receivable_lines = self.line_ids.filtered(
            lambda line: line.account_id.account_type == 'asset_receivable' and not line.reconciled
        )
        if not receivable_lines:
            return

        order_total = sum(sale_orders.mapped('amount_total'))
        if float_is_zero(order_total, precision_rounding=self.currency_id.rounding):
            return
        invoice_ratio = min(self.amount_total / order_total, 1.0)

        snapshot_vals = []
        totals = defaultdict(float)
        Snapshot = self.env['mkp.account.gateway.commission.line']
        for payment_line in sale_payment_lines:
            config = payment_line.gateway_config_id
            previous_lines = Snapshot.search([
                ('sale_payment_line_id', '=', payment_line.id),
                ('move_id', '!=', self.id),
                ('move_id.state', '=', 'posted'),
            ])
            previously_processed = sum(previous_lines.mapped('payment_amount'))
            remaining_payment = max(payment_line.payment_amount - previously_processed, 0.0)
            payment_amount = min(
                self.currency_id.round(payment_line.payment_amount * invoice_ratio),
                remaining_payment,
            )
            is_final_invoice = payment_line.order_id.invoice_status == 'invoiced'
            if is_final_invoice:
                payment_amount = remaining_payment
            if float_is_zero(payment_amount, precision_rounding=self.currency_id.rounding):
                continue

            allocation_ratio = payment_amount / payment_line.payment_amount
            component_fields = (
                'commission_amount',
                'fixed_commission_amount',
                'commission_vat_amount',
                'fixed_commission_vat_amount',
            )
            allocated_components = {}
            for field_name in component_fields:
                captured_total = payment_line[field_name]
                previously_allocated = sum(previous_lines.mapped(field_name))
                remaining_component = max(captured_total - previously_allocated, 0.0)
                component_amount = min(
                    self.currency_id.round(captured_total * allocation_ratio),
                    remaining_component,
                )
                if is_final_invoice:
                    component_amount = remaining_component
                allocated_components[field_name] = component_amount
                totals[field_name] += component_amount

            self._mkp_validate_gateway_config(config, allocated_components)
            snapshot_vals.append({
                'move_id': self.id,
                'sale_payment_line_id': payment_line.id,
                'gateway_config_id': config.id,
                'payment_amount': payment_amount,
                **allocated_components,
            })

        total_commission = sum(totals.values())
        if float_is_zero(total_commission, precision_rounding=self.currency_id.rounding):
            return
        if total_commission > self.amount_total:
            raise UserError(_(
                'Las comisiones e IVA de las pasarelas (%(commission)s) no pueden ser '
                'mayores al total de la factura (%(total)s).',
                commission=total_commission,
                total=self.amount_total,
            ))

        snapshots = Snapshot.create(snapshot_vals)
        commission_moves = self.env['account.move']
        company_currency = self.company_id.currency_id
        move_date = self.invoice_date or self.date or fields.Date.context_today(self)
        receivable_account = receivable_lines[0].account_id

        snapshots_by_journal = defaultdict(
            lambda: self.env['mkp.account.gateway.commission.line']
        )
        for snapshot in snapshots:
            snapshots_by_journal[snapshot.gateway_config_id.commission_journal_id] |= snapshot

        for journal, journal_snapshots in snapshots_by_journal.items():
            line_vals = []
            total_balance = 0.0
            for snapshot in journal_snapshots:
                config = snapshot.gateway_config_id
                components = [
                    (config.commission_expense_account_id, snapshot.commission_amount,
                     _('Comisión Pasarela - %s') % config.partner_id.display_name),
                    (config.fixed_commission_expense_account_id, snapshot.fixed_commission_amount,
                     _('Comisión Fija - %s') % config.partner_id.display_name),
                    (config.commission_vat_account_id, snapshot.commission_vat_amount,
                     _('IVA Comisión Pasarela - %s') % config.partner_id.display_name),
                    (config.fixed_commission_vat_account_id, snapshot.fixed_commission_vat_amount,
                     _('IVA Comisión Fija - %s') % config.partner_id.display_name),
                ]
                for account, amount_currency, label in components:
                    if float_is_zero(amount_currency, precision_rounding=self.currency_id.rounding):
                        continue
                    balance = self.currency_id._convert(
                        amount_currency, company_currency,
                        self.company_id, move_date,
                    )
                    total_balance += balance
                    line_vals.append((0, 0, {
                        'name': '%s - %s' % (label, self.name or self.ref or self.id),
                        'account_id': account.id,
                        'debit': balance,
                        'credit': 0.0,
                        'partner_id': config.partner_id.id,
                        'currency_id': self.currency_id.id,
                        'amount_currency': amount_currency,
                    }))

            journal_commission = sum(journal_snapshots.mapped('total_commission_amount'))
            line_vals.append((0, 0, {
                'name': _('Aplicación parcial comisiones - %s') % (self.name or self.ref or self.id),
                'account_id': receivable_account.id,
                'debit': 0.0,
                'credit': total_balance,
                'partner_id': receivable_lines[0].partner_id.id,
                'currency_id': self.currency_id.id,
                'amount_currency': -journal_commission,
            }))
            commission_move = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': journal.id,
                'date': move_date,
                'ref': _('Comisiones pasarelas de %s') % (self.name or self.ref or self.id),
                'company_id': self.company_id.id,
                'line_ids': line_vals,
            })
            commission_move.action_post()
            commission_moves |= commission_move

        lines_to_reconcile = receivable_lines | commission_moves.line_ids.filtered(
            lambda line: line.account_id == receivable_account and not line.reconciled
        )
        lines_to_reconcile.reconcile()

        unique_configs = snapshots.gateway_config_id
        self.write({
            'mkp_payment_gateway_config_id': unique_configs.id if len(unique_configs) == 1 else False,
            'mkp_gateway_commission_amount': totals['commission_amount'],
            'mkp_gateway_fixed_commission_amount': totals['fixed_commission_amount'],
            'mkp_gateway_commission_vat_amount': totals['commission_vat_amount'],
            'mkp_gateway_fixed_commission_vat_amount': totals['fixed_commission_vat_amount'],
            'mkp_gateway_commission_move_id': commission_moves[:1].id,
            'mkp_gateway_commission_move_ids': [(6, 0, commission_moves.ids)],
        })

    def _mkp_validate_gateway_config(self, config, amounts):
        if config.company_id != self.company_id:
            raise UserError(_(
                "La pasarela '%s' pertenece a una compañía distinta a la factura."
            ) % config.partner_id.display_name)
        account_requirements = (
            ('commission_amount', config.commission_expense_account_id, 'Comisión Pasarela'),
            ('fixed_commission_amount', config.fixed_commission_expense_account_id, 'Comisión Fija'),
            ('commission_vat_amount', config.commission_vat_account_id, 'IVA Comisión Pasarela'),
            ('fixed_commission_vat_amount', config.fixed_commission_vat_account_id, 'IVA Comisión Fija'),
        )
        for field_name, account, label in account_requirements:
            if amounts[field_name] and not account:
                raise UserError(_(
                    "La pasarela '%(gateway)s' no tiene cuenta para %(label)s.",
                    gateway=config.partner_id.display_name,
                    label=label,
                ))
        if not config.commission_journal_id:
            raise UserError(_(
                "La pasarela '%s' no tiene diario de comisiones."
            ) % config.partner_id.display_name)
