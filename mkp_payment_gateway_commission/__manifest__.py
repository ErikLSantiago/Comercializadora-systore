# -*- coding: utf-8 -*-
{
    'name': 'MKP Payment Gateway Commission',
    'summary': 'Payment gateway configuration and automatic commission recognition on customer invoices.',
    'version': '19.0.1.2.0',
    'category': 'Accounting/Accounting',
    'author': 'OpenAI',
    'license': 'LGPL-3',
    'depends': [
        'sale_management',
        'account',
    ],
    'data': [
        'security/payment_gateway_security.xml',
        'security/ir.model.access.csv',
        'views/payment_gateway_config_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
}
