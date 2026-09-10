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

    producteca_shippingLink_attachment_ok = fields.Boolean(string="Ok",default=False)

    def producteca_clean_print( self, max=None, date=None ):
        _logger.info("stock.picking_type producteca_clean_print START")
        sps = self.env["stock.picking"].search([
                    ('producteca_shippingLink_attachment','!=',None),
                    ('producteca_shippingLink_attachment_ok','=',False)])

        cMmax = max or 100
        if sps:
            _logger.info("stock.picking_type producteca_clean_print sps:"+str(len(sps))+" max:"+str(cMmax))
        cn = 0
        cM = 0

        for sp in sps:
            cn+=1
            cM+=1
            pris = self.env['ir.attachment'].search([('res_id','=',sp.id),
                                ('res_model','=','stock.picking'),
                                ('mimetype','=','application/pdf')])
            if pris and len(pris)>1:
                for pri in pris:
                    if sp.producteca_shippingLink_attachment!=pri:
                        _logger.info("stock.picking_type producteca_clean_print date:"+str(pri.name)+" "+str(pri.create_date))
                        pri.unlink()
                sp.producteca_shippingLink_attachment_ok = True
            else:
                sp.producteca_shippingLink_attachment_ok = True
            if cn>10:
                _logger.info("stock.picking_type producteca_clean_print commit")
                self.env.cr.commit()
                cn = 0
            if cM>cMmax:
                break;

        sos = self.env["sale.order"].search([
                    ('producteca_shippingLink_attachment','!=',None),
                    ('producteca_shippingLink_attachment_ok','=',False)])

        if sos:
            _logger.info("sale.order producteca_clean_print sos:"+str(len(sos))+" max:"+str(cMmax))
        cn = 0
        cM = 0

        for so in sos:
            cn+=1
            cM+=1
            pris = self.env['ir.attachment'].search([('res_id','=',so.id),
                                ('res_model','=','sale.order'),
                                ('mimetype','=','application/pdf')])
            if pris and len(pris)>1:
                for pri in pris:
                    if so.producteca_shippingLink_attachment!=pri:
                        _logger.info("sale.order producteca_clean_print date:"+str(pri.name)+" "+str(pri.create_date))
                        pri.unlink()
                so.producteca_shippingLink_attachment_ok = True
            else:
                so.producteca_shippingLink_attachment_ok = True
            if cn>10:
                _logger.info("sale.order producteca_clean_print commit")
                self.env.cr.commit()
                cn = 0
            if cM>cMmax:
                break;

        _logger.info("stock.picking_type producteca_clean_print END")

    def producteca_clean_old_print( self, max=None, date=None ):
        _logger.info("stock.picking_type producteca_clean_old_print START date:"+str(date))
        if date:
            cMmax = max or 100
            pris = None
            prisSP = self.env['ir.attachment'].search([('name','ilike','Shipment_PR%'),
                ('res_model','=','stock.picking'),
                ('mimetype','=','application/pdf'),
                ('create_date','<',date)],limit=cMmax/2)
            prisSO = self.env['ir.attachment'].search([('name','ilike','Shipment_PR%'),
                ('res_model','=','sale.order'),
                ('mimetype','=','application/pdf'),
                ('create_date','<',date)],limit=cMmax/2)
            _logger.info("stock.picking_type producteca_clean_old_print prisSP:"+str(len(prisSP)))
            _logger.info("stock.picking_type producteca_clean_old_print prisSO:"+str(len(prisSO)))
            pris = prisSP+prisSO
            #sqls = "select id, name, create_date, store_fname from ir_attachment where res_model = 'stock.picking' and mimetype = 'application/pdf' and create_date < '"+str(date)+"' and name ilike 'Shipment_PR%'"
            #_logger.info("sqls:"+str(sqls))
            #respb = self._cr.execute(sqls)
            #_logger.info("respb:"+str(respb))
            if pris:
                cn = 0
                cM = 0
                _logger.info("stock.picking_type producteca_clean_old_print pris:"+str(len(pris)))
                for pri in pris:
                    _logger.info("stock.picking_type producteca_clean_old_print date:"+str(pri.name)+" "+str(pri.create_date))
                    cn+=1
                    cM+=1
                    pri.unlink()
                    if cn>10:
                        _logger.info("stock.picking_type producteca_clean_old_print commit")
                        self.env.cr.commit()
                        cn = 0
                    if cM>cMmax:
                        break;

        _logger.info("stock.picking_type producteca_clean_old_print END date:"+str(date))

    def producteca_print(self):
        _logger.info("stock.picking_type producteca_print")
        sale_order = self.sale_id
        pso = sale_order and sale_order.producteca_binding
        #self.producteca_clean_print()
        #_logger.info("stock.picking_type producteca_print PSO: "+str(pso))
        #_logger.info("stock.picking_type producteca_print producteca_shippingLink_attachment: "+str(self.producteca_shippingLink_attachment))
        if pso and pso.shippingLink and not self.producteca_shippingLink_attachment:
            #_logger.info("stock.picking_type producteca_print PRINTING")
            ret = pso.shippingLinkPrint()
            #_logger.info("stock.picking_type producteca_print PRINTING RET"+str(ret))
            if ret and 'name' in ret:
                _logger.error(ret)
                return ret

            mimetype = 'application/pdf'
            if pso.shippingLink and "zpl" in pso.shippingLink:
                mimetype = 'x-application/zpl'

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
                'mimetype': mimetype
            })
            if attachment:
                self.producteca_shippingLink_attachment = attachment.id

class StockMove(models.Model):
    _inherit = "stock.move"

    def producteca_update_boms( self  ):
        #config = config or self.env.user.company_id
        company_ids = self.env.user.company_ids
        mov = self

        _logger.info("producteca_update_boms > "+str(company_ids))

        if mov.product_id:

            product_id = mov.product_id

            config = None
            is_producteca = False

            for binding in mov.product_id.producteca_bindings:
                account = binding.connection_account
                config = account and account.configuration
                if not config:
                    break;

                #product_id.process_producteca_stock_moves_update()
                is_producteca = (binding)

                if (config and config.publish_stock and is_producteca):
                    #_logger.info("meli_update_boms > mercadolibre_cron_post_update_stock "+str(config and config.name))
                    product_id.producteca_post_stock(account=account,stock_move=self)

            #sin config, recorremos las companias a las que forma parte este producto
            if not config and company_ids:
                for comp in company_ids:
                    is_company = (product_id.company_id==False or product_id.company_id==comp)
                    if (is_company):
                        for account in comp.producteca_connections:
                            config = account and account.configuration
                            #_logger.info("is_company: "+str(is_company)+" product_id.company_id:"+str(product_id.company_id)+" comp:"+str(comp))
                            #_logger.info("is_meli: "+str(is_meli)+" comp.mercadolibre_cron_post_update_stock:"+str(comp.mercadolibre_cron_post_update_stock))
                            if (config and config.publish_stock and is_company and is_producteca):
                                product_id.producteca_post_stock(account=account,stock_move=self)



            #BOM SECTION POST STOCK if needed

            if not ("mrp.bom" in self.env):
                return False

            bomlines = "bom_line_ids" in product_id._fields and product_id.bom_line_ids
            bomlines = bomlines or self.env['mrp.bom.line'].search([('product_id','=',product_id.id)])
            bomlines = bomlines or []

            config = None
            bm_is_producteca = False

            for bomline in bomlines:

                bm_product_id = bomline.bom_id and bomline.bom_id.product_id
                #bm_is_meli = (bm_product_id.meli_id and bm_product_id.meli_pub)
                for binding in mov.product_id.producteca_bindings:
                    account = binding.connection_account
                    config = account and account.configuration
                    if not config:
                        break;

                    bm_is_producteca = (binding)

                    if (config and config.publish_stock and bm_product_id and bm_is_producteca):
                        bm_product_id.producteca_post_stock(account=account,stock_move=self)

                #sin config, recorremos las companias a las que forma parte este producto
                if not config and company_ids and bm_product_id:

                    bindings = bm_product_id.producteca_bindings

                    for comp in company_ids:
                        bm_is_company = (bm_product_id.company_id==False or bm_product_id.company_id==comp)
                        bm_is_producteca = (bindings)
                        for binding in bindings:
                            account = binding.connection_account
                            config = account and account.configuration
                            if (config and config.publish_stock and bm_is_company and bm_is_producteca):
                                bm_product_id.producteca_post_stock(account=account,stock_move=self)

        return True

    def _action_assign(self):
        company = self.env.user.company_id

        res = super(StockMove, self)._action_assign()

        for mov in self:
            mov.producteca_update_boms()

        return res


    def _action_done(self, cancel_backorder=False):
        #import pdb; pdb.set_trace()
        #_logger.info("Stock move: meli_oerp > _action_done")
        company = self.env.user.company_id
        moves_todo = super(StockMove, self)._action_done(cancel_backorder=cancel_backorder)

        for mov in self:
            mov.producteca_update_boms()

        return moves_todo
