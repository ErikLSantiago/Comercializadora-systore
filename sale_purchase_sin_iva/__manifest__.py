# -*- coding: utf-8 -*-
{
    'name': 'Sin IVA en formulario (Ventas y Compras)',
    'summary': 'Añade pestaña "Sin IVA" a Pedidos de Venta y de Compra con cálculos sin IVA. Sin reportes PDF.',
    'version': '18.0.1.5',
    'license': 'LGPL-3',
    'author': 'ChatGPT',
    'depends': ['sale_management', 'purchase'],
    'data': [
        'views/sale_sin_iva_views.xml',
        'views/purchase_sin_iva_views.xml',
    ],
    'installable': True,
    'application': False,
}