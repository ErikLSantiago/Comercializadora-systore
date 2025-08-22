# -*- coding: utf-8 -*-
from . import models
from . import controllers

from odoo import api, SUPERUSER_ID

def post_init(env):
    # Crea menú /quote si no existe
    try:
        Website = env['website'].search([], limit=1)
        parent_menu = env.ref('website.main_menu', raise_if_not_found=False)
        if not parent_menu and Website and Website.menu_id:
            parent_menu = Website.menu_id
        Menu = env['website.menu']
        existing = Menu.search([('url', '=', '/quote')], limit=1)
        if not existing:
            vals = {
                'name': 'Solicitar Cotización',
                'url': '/quote',
                'parent_id': parent_menu.id if parent_menu else False,
                'sequence': 60,
            }
            if Website and hasattr(Menu, 'website_id'):
                vals['website_id'] = Website.id
            Menu.create(vals)
    except Exception:
        pass
