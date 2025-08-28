# -*- coding: utf-8 -*-

import base64
from odoo import http, api
from odoo import fields, osv
from odoo.http import Controller, Response, request, route
import pdb
import logging
_logger = logging.getLogger(__name__)

from odoo.addons.odoo_connector_api.controllers.main import OcapiAuthorize
from odoo.addons.odoo_connector_api.controllers.main import OcapiCatalog

import json
from odoo.tools import date_utils
try:
    json_default = date_utils.json_default
except:
    from odoo.tools import json_default
    pass;
import base64

import hashlib
from datetime import datetime

class ProductecaAuthorize(OcapiAuthorize):

    @http.route()
    def authorize(self, connector, **post):
        _logger.info("connector:"+str(connector))
        if connector and connector=="producteca":
            return self.producteca_authorize(**post)
        else:
            return super(OcapiAuthorize, self).authorize( connector, **post )

    def producteca_authorize(self, **post):
        #POST api user id and token, create id based on URL if need to create one
        #check all connectors
        #_logger.info("post:"+str(post))
        client_id = post.get("client_id") or post.get("app_id")
        secret_key = post.get("secret_key") or post.get("app_key")
        connection_account = []
        if client_id and secret_key:
            _logger.info("Authentication request for producteca")
            connection_account = request.env['producteca.account'].sudo().search([('client_id','=',client_id),('secret_key','=',secret_key)])
        access_tokens = []
        if not connection_account:
            _logger.error("No response for: client_id:"+str(client_id)+" secret_key:" + str(secret_key) )
        for a in connection_account:
            _logger.info("Trying")
            access_token = a.authorize_token( client_id, secret_key )
            access_tokens.append({ 'client_id': client_id, 'access_token': access_token  })
        _logger.info(access_tokens)
        return access_tokens

    @http.route()
    def status(self, connector, **post):

        _logger.info("odoo_connector_api_producteca > status : connector: "+str(connector))
        #POST api user id and token, create id based on URL if need to create one
        #check all connectors
        client_id = post.get("client_id") or post.get("app_id")
        secret_key = post.get("secret_key") or post.get("app_key")

        connection_account = []
        access_status = []


        if not (connector=="producteca"):
            access_status = super(ProductecaAuthorize, self).status(connector, **post )
            return access_status

        if client_id and secret_key:
            _logger.info("Status request for connector: "+str(connector)+ " client:"+str(client_id)+" secret_key:"+str(secret_key))
            connection_account = request.env['producteca.account'].sudo().search([('client_id','=',client_id),('secret_key','=',secret_key)], limit=1)
            _logger.info("Status request for connector: connection_account: "+str(connection_account))

        if not connection_account:
            status_error_message = "Status request for connector IMPOSSIBLE, account not accessible, no client id or secret_key. "+str(connector)+ " client:"+str(client_id)+" secret_key:"+str(secret_key)
            _logger.info(status_error_message)
            access_status.append({ "error": status_error_message })

        if connection_account:
            access_status+= connection_account.fetch_status()

        return access_status

class ProductecaCatalog(OcapiCatalog):

    def get_producteca_connection(self, **post):

        _logger.info("get_producteca_connection")

        connector = "producteca"
        connection_account = None

        access_token = post.get("access_token")
        secret_key = post.get("secret_key")
        client_id = post.get("client_id")

        if not access_token and not secret_key and not client_id:
            return False

        if access_token:
            _logger.info("get_producteca_connection access_token:"+str(access_token))

            connection_account = request.env['producteca.account'].sudo().search([('access_token','=ilike',access_token)])

        if client_id and secret_key and not connection_account:
            connection_account = request.env['producteca.account'].sudo().search([('client_id','=ilike',client_id),('secret_key','=ilike',secret_key)])

        if client_id and not connection_account:
            connection_account = request.env['producteca.account'].sudo().search([('client_id','=ilike',client_id)])

        _logger.info("get_producteca_connection:"+str(connection_account))

        if not connection_account or not len(connection_account)==1:
            return False

        if not (connector == connection_account.type):
            return False

        _logger.info("return connection_account:"+str(connection_account))
        return connection_account

    @http.route()
    def get_connection_account(self, connector,**post):
        if connector and connector=="producteca":
            return self.get_producteca_connection(**post)
        else:
            return super(OcapiCatalog, self).get_connection(connector,**post)

    @http.route('/ocapi/<string:connector>/<string:channel>/status', auth='public', type='json', methods=['POST','GET'], csrf=False, cors='*')
    def status(self, connector, channel, **post):
        _logger.info("producteca status: connector:"+str(connector)+" channel:"+str(channel))
        _logger.info("producteca status: post:"+str(post))
        connection = self.get_connection_account(connector,**post)

        if not connection:
            error = {"error": "connection not found"}
            return error

        #filter products using connection account and configuration bindings
        _logger.info("producteca status calling fetch_status:"+str(connection))
        return connection.fetch_status(**post)
