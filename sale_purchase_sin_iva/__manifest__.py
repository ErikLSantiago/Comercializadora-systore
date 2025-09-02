# -*- coding: utf-8 -*-
{
    'name': 'Sin IVA en formulario + Reporte nuevo (Ventas/Compras)',
    'summary': 'Agrega columna/total Sin IVA en formularios y nuevos reportes imprimibles para Venta y Compra.',
    'version': '18.0.1.4',
    'license': 'LGPL-3',
    'author': 'Custom',
    'website': '',
    'category': 'Sales/Purchase',
    'depends': ['sale_management', 'purchase'],
    'data': [
        'views/sale_sin_iva_views.xml',
        'views/purchase_sin_iva_views.xml',
        'report/sin_iva_reports.xml',
        'report/report_saleorder_siniva_template.xml',
        'report/report_purchaseorder_siniva_template.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
