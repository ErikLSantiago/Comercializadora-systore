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

import requests

class stock_location(models.Model):
    
    _inherit = "stock.location"
    
    producteca_logistic_type = fields.Char(string="Logistic Type Asociado (Producteca)",index=True)
    
class stock_warehouse(models.Model):
    
    _inherit = "stock.warehouse"
    
    producteca_logistic_type = fields.Char(string="Logistic Type Asociado (Producteca)",index=True)
    
class stock_picking(models.Model):
    
    _inherit = "stock.picking"
    
    producteca_shippingLink_attachment = fields.Many2one(
            'ir.attachment',
            string='Guia Pdf Adjunta',
            copy=False
        )
    
    def producteca_print(self):
        _logger.info("stock.picking_type producteca_print")
        sale_order = self.sale_id
        pso = sale_order and sale_order.producteca_binding
        if pso:
            ret = pso.shippingLinkPrint()
            if ret and 'name' in ret:
                _logger.error(ret)
                return ret
                
            ATTACHMENT_NAME = "Shipment_"+sale_order.name
            b64_pdf = pso.shippingLink_pdf_file
            attachment = self.env['ir.attachment'].create({
                'name': ATTACHMENT_NAME,
                'type': 'binary',
                'datas': b64_pdf,
                #'datas_fname': ATTACHMENT_NAME + '.pdf',
                #'store_fname': ATTACHMENT_NAME,
                'res_model': "stock.picking",
                'res_id': self.id,
                'mimetype': 'application/pdf'
            })
            if attachment:
                self.producteca_shippingLink_attachment = attachment.id
    
