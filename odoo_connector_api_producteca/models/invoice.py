# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import fields, osv, models, api
from odoo.tools.translate import _
import logging
_logger = logging.getLogger(__name__)
import pdb
from .warning import warning
import requests
import base64
from .versions import *
from odoo.exceptions import UserError, ValidationError

class Invoice(models.Model):

    _inherit = acc_inv_model

    producteca_mail = fields.Char(string="Producteca mail")
    producteca_inv_attachment_id = fields.Many2one(
        'ir.attachment',
        string='Factura Archivo Adjunto',
        copy=False
    )
    producteca_order_binding_id = fields.Many2one( "producteca.sale_order", string="Producteca Sale Order" )
    #account_payment_group_id = fields.Many2one( "account.payment.group", related="producteca_order_binding_id.account_payment_group_id", string="Pago agrupado" )

    def update_order_producteca(self):
        pso = self.producteca_order_binding_id
        if pso:
            ret = pso.update()
            if ret and 'name' in ret:
                _logger.error(ret)
                return ret

    def enviar_factura_producteca(self, reenviar=False):

        _logger.info("Enviar factura a producteca reenviar:"+str(reenviar))

        template = self.env.ref('odoo_connector_api_producteca.producteca_invoice_email_template', False )
        _logger.info(template)
        sale_order = self.env['sale.order'].search([('name', '=', get_invoice_origin(self) )], limit=1 )

        self.producteca_order_binding_id = sale_order and sale_order.producteca_bindings and sale_order.producteca_bindings[0]
        if not self.producteca_order_binding_id:
            _logger.error("Error no order binding")
            return {}

        pso = self.producteca_order_binding_id
        channel_binding = pso and pso.channel_binding_id



        if reenviar==True:
            render_message = "Reenviando mail producteca"
            if sale_order:
                sale_order.message_post( body = render_message )
            self.producteca_inv_attachment_id = None

        if not self.producteca_inv_attachment_id:
            ATTACHMENT_NAME = "FACTURA "+self.display_name

            _logger.info(ATTACHMENT_NAME)
            render_message = "Generando reporte factura para enviar mail a producteca: "+str(ATTACHMENT_NAME)
            if sale_order:
                sale_order.message_post( body = render_message )

            REPORT_ID = 'account.report_invoice'
            report = self.env['ir.actions.report']._get_report_from_name(REPORT_ID)

            #custom report
            invoice_report_id = (channel_binding and "invoice_report_id" in channel_binding._fields and channel_binding.invoice_report_id) or None

            report = invoice_report_id or report


            res_ids = self.ids
            rendering_message = "Rendering qweb pdf with: report:"+str(report)+" and res_ids:"+str(self)+" ids:"+str(res_ids)
            _logger.info(rendering_message)
            if sale_order:
                sale_order.message_post( body = rendering_message )
            try:
                user_id_id = sale_order.user_id and sale_order.user_id.id
                pdf = render_qweb_pdf( report.sudo().with_user(user_id_id), report_ref=report.id,res_ids=res_ids)
                if pdf and sale_order:
                    rendering_message = "Pdf renderizado ok"
                    sale_order.message_post( body = rendering_message )
            except Exception as E:
                rendering_error = rendering_message+ " Error: "+str(E)
                _logger.error(rendering_error)
                if sale_order:
                    sale_order.message_post( body = rendering_error )
                return False

            b64_pdf = base64.b64encode(pdf[0])

            attachment = self.env['ir.attachment'].create({
                'name': ATTACHMENT_NAME,
                'type': 'binary',
                'datas': b64_pdf,
                #'datas_fname': ATTACHMENT_NAME + '.pdf',
                'store_fname': ATTACHMENT_NAME,
                'res_model': acc_inv_model,
                'res_id': self.id,
                'mimetype': 'application/pdf'
            })
            if attachment:
                if b64_pdf and sale_order and attachment:
                    rendering_message = "Pdf adjuntado ok"
                    sale_order.message_post( body = rendering_message )
                self.producteca_inv_attachment_id = attachment.id

        self.producteca_mail = self.producteca_mail or self.producteca_order_binding_id.mail or (self.producteca_order_binding_id.client and self.producteca_order_binding_id.client.mail)
        if not self.producteca_mail:
            render_error = "Error no mail from binding, fix."
            _logger.error(render_error)
            if sale_order:
                sale_order.message_post( body = render_error )
            return

        archivos_ids=[]
        archivos_ids.append(self.producteca_inv_attachment_id.id)

        if template:
            if not template.email_from:
                template.email_from = str(self.company_id.email)
            template.attachment_ids = [(5, 0, [])]
            if archivos_ids:
                template.attachment_ids = [(6, 0, archivos_ids)]
            try:
                res = template.send_mail(self.id, force_send=True)
                template.attachment_ids = [(5, 0, [])]
                if sale_order and res:
                    rendering_message = "Factura enviada ok "+str(res)
                    sale_order.message_post( body = rendering_message )
            except Exception as E:
                template.attachment_ids = [(5, 0, [])]
                rendering_error = "Error al enviar correo, revise los correos en Ajustes > Tecnico > Correos electronicos y este mensaje: "+str(E)
                _logger.error(rendering_error)
                if sale_order:
                    sale_order.message_post( body = rendering_error )
                return False



    def conciliar_factura_producteca(  self ):
        #based on _compute_payments_widget_to_reconcile_info
        move = self

        _logger.info("Conciliar factura producteca:"+str(move and move.name))

        if not move:
            return

        pay_term_lines = move.line_ids\
            .filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))

        _logger.info("Conciliar factura producteca pay_term_lines:"+str(pay_term_lines))

        if not pay_term_lines:
            return



        if move.state != 'posted' \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
            return

        #TODO es que si la factura esta a nombre de un usuario generico, como se debita el pago, el pago tambien debe hacerse al usuario generico....
        #TODO filtrar segun referencia de orden/factura PR-XXXXX-ML-YYYYY
        domain = [
                ('account_id', 'in', pay_term_lines.account_id.ids),
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', move.commercial_partner_id.id),
                ('reconciled', '=', False),
                '|', ('amount_residual', '!=', 0.0), ('amount_residual_currency', '!=', 0.0),
            ]

        payments_widget_vals = {'outstanding': True, 'content': [], 'move_id': move.id}

        if move.is_inbound():
            domain.append(('balance', '<', 0.0))
            payments_widget_vals['title'] = _('Outstanding credits')
        else:
            domain.append(('balance', '>', 0.0))
            payments_widget_vals['title'] = _('Outstanding debits')

        for line in self.env['account.move.line'].search(domain):

            if line.currency_id == move.currency_id:
                # Same foreign currency.
                amount = abs(line.amount_residual_currency)
            else:
                # Different foreign currencies.
                amount = move.company_currency_id._convert(
                    abs(line.amount_residual),
                    move.currency_id,
                    move.company_id,
                    line.date,
                )

            if move.currency_id.is_zero(amount):
                continue

            payments_widget_vals['content'].append({
                'journal_name': line.ref or line.move_id.name,
                'amount': amount,
                'currency_id': move.currency_id.id,
                'id': line.id,
                'move_id': line.move_id.id,
                'date': fields.Date.to_string(line.date),
                'account_payment_id': line.payment_id.id,
            })


        _logger.info("Conciliar factura producteca payments_widget_vals:"+str(payments_widget_vals))
        if not payments_widget_vals['content']:
            return

        #based on def js_assign_outstanding_line(self, line_id):
        for payments_val in payments_widget_vals['content']:
            line_id = payments_val['id']
            lines = self.env['account.move.line'].browse(line_id)
            lines += self.line_ids.filtered(lambda line: line.account_id == lines[0].account_id and not line.reconciled)
            lines.reconcile()


    def producteca_fix_invoice( self, val, pso ):
        if (pso and pso.channel_binding_id and type(val)==dict):
            if (not "l10n_mx_edi_usage" in val and "l10n_mx_edi_usage" in pso.channel_binding_id._fields):
                val["l10n_mx_edi_usage"] = pso.channel_binding_id.l10n_mx_edi_usage
            if (not "l10n_mx_edi_payment_method_id" in val and "l10n_mx_edi_payment_method_id" in pso.channel_binding_id._fields):
                val["l10n_mx_edi_payment_method_id"] = pso.channel_binding_id.l10n_mx_edi_payment_method_id and pso.channel_binding_id.l10n_mx_edi_payment_method_id.id

        return val

    @api.model_create_multi
    def create(self, vals_list):
        #_logger.info("vals_list: "+str(vals_list))
        if (vals_list and type(vals_list)==list):
            for vi in range( 0, len(vals_list) ):
                val = vals_list[vi]
                if val:
                    ref = 'ref' in val and val['ref']

                    if ( ref and "PR-" in ref ):
                        if (", " in ref):
                            refsplit = ref.split(", ")
                            ref = type(refsplit)==list and refsplit and refsplit[0]

                        pso = self.env["producteca.sale_order"].search([('name','like',ref)], limit=1)
                        if (pso and not 'producteca_order_binding_id' in val):
                            vals_list[vi]['producteca_order_binding_id'] =  pso.id
                        else:
                            _logger.info("Error ref no encontrada:"+str(ref))

                        if (pso):
                            vals_list[vi] = self.producteca_fix_invoice( val, pso )

        #_logger.info("vals_list: "+str(vals_list) )
        rslt = super(Invoice, self).create(vals_list)
        #_logger.info("rslt: "+str(rslt))
        return rslt
    #def action_post( self ):
    #    super( Invoice, self ).action_post()
