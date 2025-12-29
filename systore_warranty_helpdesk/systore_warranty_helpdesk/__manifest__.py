# -*- coding: utf-8 -*-
{
    'name': 'Systore Warranty Helpdesk',
    'version': '18.0.2.14.46',
    'category': 'Website/Helpdesk',
    'summary': 'Warranty request flow integrated with Helpdesk + Website (Systore).',
    'author': 'Systore',
    'license': 'LGPL-3',
    'depends': ['website', 'helpdesk', 'sale_management', 'google_recaptcha'],
    'data': [
        'security/ir.model.access.csv',
        'views/helpdesk_team_data.xml',
        'views/helpdesk_ticket_views.xml',
        'views/warranty_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'systore_warranty_helpdesk/static/src/js/warranty_recaptcha.js',
        ],
    },
    'installable': True,
    'application': False,
}
