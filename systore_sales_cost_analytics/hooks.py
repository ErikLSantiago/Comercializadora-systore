# -*- coding: utf-8 -*-
def post_init_hook(env):
    Channel = env['systore.sales.channel'].sudo()
    Account = env['account.account'].sudo()
    mappings = {
        'Marketplace': {'401.01.01','401.01.03','401.01.04','401.01.04.01','401.01.05','401.01.06','401.01.07','401.01.08','401.01.13','401.01.14','401.01.15','401.01.20','401.01.21'},
        'Mayoreo': {'401.01.10','402.01.10'},
        'Empleado': {'401.01.12','401.01.16'},
    }
    for name, codes in mappings.items():
        channel = Channel.search([('name','=',name)], limit=1)
        if channel:
            Account.search([('code','in',list(codes))]).write({'systore_sales_channel_id': channel.id})
