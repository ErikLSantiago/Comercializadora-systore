# -*- coding: utf-8 -*-
{
    "name": "Meat Cutting - Precio por Peso (Reserva)",
    "version": "18.0.1.0.0",
    "category": "Inventory/Sales",
    "summary": "Calcula precio de venta en función del peso del número de serie al reservar (assign).",
    "depends": ["sale_stock", "stock", "uom", "meat_cutting"],
    "data": [
        "views/product_views.xml",
        "views/sale_order_views.xml",
    ],
    "license": "LGPL-3",
    "application": False,
    "installable": True,
}
