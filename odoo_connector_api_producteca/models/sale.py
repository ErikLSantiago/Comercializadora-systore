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
from .versions import *

class SaleOrder(models.Model):

    _inherit = "sale.order"

    #mercadolibre could have more than one associated order... packs are usually more than one order
    producteca_bindings = fields.Many2many( "producteca.sale_order", string="Producteca Connection Bindings" )
    producteca_update_forbidden = fields.Boolean(string="Bloqueado para actualizar desde Producteca",default=False, index=True)

    def _producteca_binding( self ):
        for so in self:
            so.producteca_binding = so.producteca_bindings and so.producteca_bindings[0]

    producteca_binding = fields.Many2one( "producteca.sale_order", string="Producteca Sale Order",compute=_producteca_binding )


    @api.depends('producteca_bindings')
    def _producteca_sale_order( self ):
        for so in self:
            so.producteca_sale_order = (so.producteca_bindings and so.producteca_bindings[0]) or None
    producteca_sale_order = fields.Many2one( "producteca.sale_order", string="Producteca Sale Order", compute=_producteca_sale_order, store=True, index=True )

    @api.depends('producteca_bindings')
    def _producteca_channel_binding( self ):
        for so in self:
            so.producteca_sale_order = (so.producteca_bindings and so.producteca_bindings[0]) or None
            so.producteca_channel_binding = (so.producteca_sale_order and so.producteca_sale_order.channel_binding_id) or None
            
    producteca_channel_binding = fields.Many2one( "producteca.channel.binding", string="Channel", compute=_producteca_channel_binding, store=True, index=True  )
    
    @api.depends('producteca_bindings')
    def _producteca_sale_order_account( self ):
        for so in self:
            so.producteca_sale_order = (so.producteca_bindings and so.producteca_bindings[0]) or None
            so.producteca_channel_binding = (so.producteca_sale_order and so.producteca_sale_order.channel_binding_id) or None
            so.producteca_sale_order_account = (so.producteca_sale_order and so.producteca_sale_order.connection_account) or None
    producteca_sale_order_account = fields.Many2one( "producteca.account", string="Producteca Account", compute=_producteca_sale_order_account, store=True, index=True  )

    def _producteca_update_needed(self):
        for so in self:
            so.producteca_update_needed = True
            if (so.producteca_bindings and (not so.producteca_sale_order or not so.producteca_channel_binding or not so.producteca_sale_order_account)):
                so._producteca_sale_order_account()
                so.producteca_update_needed = False
                
    producteca_update_needed = fields.Boolean(string="Test Update Needed",compute=_producteca_update_needed)

    #etiqueta analitica con etiqueta (asociada al canal)
    #cuenta analitica > se asocia la cuenta (producteca.account)

    producteca_shippingLink_pdf_file_rel = fields.Binary(related="producteca_binding.shippingLink_pdf_file",string="Guia PDF")
    producteca_shippingLink_pdf_file = fields.Binary(string="Guia (Producteca)",attachment=True,index=True)
    producteca_shippingLink_pdf_filename = fields.Char(string="Guia (Producteca) Filename",index=True)
    producteca_shippingLink_attachment =  fields.Many2one(
            'ir.attachment',
            string='Guia Pdf Adjunta',
            copy=False
        )

    producteca_logistic_type = fields.Char(string="Logistic Type (Producteca)",related="producteca_sale_order.logisticType", index=True)

    def producteca_update( self, context=None ):
        _logger.info("producteca_update:"+str(self))
        context = context or self.env.context
        for so in self:
            if so.producteca_bindings:
                pso = so.producteca_bindings[0]
                if pso:
                    ret = pso.update()
                    if ret and 'name' in ret:
                        _logger.error(ret)
                        return ret

    def producteca_print( self, context=None ):
        _logger.info("producteca_print:"+str(self))
        context = context or self.env.context
        for so in self:
            if so.producteca_bindings:
                pso = so.producteca_bindings[0]
                if pso:
                    ret = pso.shippingLinkPrint()
                    if ret and 'name' in ret:
                        _logger.error(ret)
                        return ret

    def producteca_deliver( self ):
        _logger.info("producteca_deliver")
        res= {}
        if self.picking_ids:
            for spick in self.picking_ids:
                _logger.info(spick)

                _logger.info("producteca_deliver > validating")
                try:
                    _logger.info("producteca_deliver > button_validate")
                    _logger.info(spick.move_line_ids)
                    if (spick.move_line_ids):
                        _logger.info(spick.move_line_ids)
                        if (len(spick.move_line_ids)>=1):
                            for pop in spick.move_line_ids:
                                _logger.info(pop)
                                if (pop.qty_done==0.0 and pop.product_qty>=0.0):
                                    pop.qty_done = pop.product_qty
                    res = spick.sudo().button_validate()
                    #res = spick.sudo()._action_done()
                    _logger.info("producteca_deliver > button_validate res: "+str(res))
                    continue;
                except Exception as e:
                    _logger.error("producteca_deliver > stock pick button_validate/action_done error >> "+str(e))
                    res = { 'error': str(e) }
                    pass;

                try:
                    _logger.info("producteca_deliver > action_assign")
                    spick.sudo().action_assign()
                    _logger.info("producteca_deliver > button_validate")
                    _logger.info(spick.move_line_ids)
                    if (spick.move_line_ids):
                        _logger.info(spick.move_line_ids)
                        if (len(spick.move_line_ids)>=1):
                            for pop in spick.move_line_ids:
                                _logger.info(pop)
                                if (pop.qty_done==0.0 and pop.product_qty>=0.0):
                                    pop.qty_done = pop.product_qty
                    res = spick.sudo().button_validate()
                    #spick.sudo()._action_done()
                    _logger.info("producteca_deliver > button_validate res: "+str(res))
                    continue;
                except Exception as e:
                    _logger.error("stock pick action_assign/button_validate/action_done error >> "+str(e))
                    res = { 'error': str(e) }
                    pass;
        return res

    def action_invoice_create(self, grouped=False, final=False):
        order = self

        #simulate invoice creation
        invoice_vals_list = []
        invoice_vals = order._prepare_invoice()
        invoiceable_lines = order._get_invoiceable_lines(final=False)
        _logger.info("_prepare_invoice:"+str(invoice_vals))
        _logger.info("_get_invoiceable_lines:"+str(invoiceable_lines))
        invoice_line_vals = []
        invoice_item_sequence = 0
        for line in invoiceable_lines:
            invoice_line_vals.append(
                (0, 0, line._prepare_invoice_line(
                    sequence=invoice_item_sequence,
                )),
            )
            invoice_item_sequence += 1
        invoice_vals['invoice_line_ids'] += invoice_line_vals
        #invoice_vals_list.append(invoice_vals)
        _logger.info("invoice_line_vals:"+str(invoice_line_vals))

        invoice_vals_list.append(invoice_vals)
        _logger.info("invoice_vals_list:"+str(invoice_vals_list))
        invoice_vals_list = self.env["account.move"]._move_autocomplete_invoice_lines_create(invoice_vals_list)
        _logger.info("invoice_vals_list:"+str(invoice_vals_list))

        #real creation
        _invoices = order_create_invoices( super(SaleOrder,self).with_context({'default_journal_id': invoice_vals['journal_id'] }), grouped=grouped, final=final )

        return _invoices

class SaleOrderLine(models.Model):

    _inherit = "sale.order.line"

    #here we must use Many2one more accurate, there is no reason to have more than one binding (more than one account and more than one item/order associated to one sale order line)
    producteca_bindings = fields.Many2one( "producteca.sale_order_line", string="Producteca Connection Bindings" )

class ResPartner(models.Model):

    _inherit = "res.partner"

    #several possible relations? we really dont know for sure, how to not duplicate clients from different platforms
    #besides, is there a way to identify duplicates other than integration ids
    producteca_bindings = fields.Many2many( "producteca.client", string="Producteca Connection Bindings" )

#Odoo 15.0 Only
class AccountPaymentMethod(models.Model):
    _inherit = 'account.payment.method'

    @api.model
    def _get_payment_method_information(self):
        res = super()._get_payment_method_information()
        res['outbound_online_producteca'] = {'mode': 'multi', 'domain': [('type', '=', 'bank')]}
        res['inbound_online_producteca'] = {'mode': 'multi', 'domain': [('type', '=', 'bank')]}
        return res
