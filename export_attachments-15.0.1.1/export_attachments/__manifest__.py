# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Export Attachments',
    'author': 'Hariprasath.B',
    'depends': [
        'web',
        'base'
    ],
    'version': '15.0.1.1',
    'description': """
        Export Attachments
        In Odoo, We can export all fields but binary fields is very hard to download for many records at once. So planned to give a solution fot that.
    """,
    'summary': 'Export Attachments',
    'category': 'Tools',
    'license': 'OPL-1',
    'website': '',
    'price': '20',
    'currency': 'EUR',
    'sequence': 1,
    'data': [
        'security/ir.model.access.csv',
        'views/export_attachments_view.xml',
    ],
    'qweb': [
    ],
    'images': ['images/screen.gif', 'images/screen.png', 'images/screen-version.png'],
    'application': True,
    'installable': True,
}
