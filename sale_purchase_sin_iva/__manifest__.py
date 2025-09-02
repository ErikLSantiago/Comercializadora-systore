{
    "name": "Sin IVA en formulario + Reporte nuevo (Ventas/Compras)",
    "summary": "Añade pestaña 'Sin IVA' en ventas/compras y reportes PDF dedicados.",
    "version": "18.0.1.3",
    "license": "LGPL-3",
    "author": "ChatGPT",
    "website": "https://example.com",
    "depends": ["sale", "purchase"],
    "data": [
        "views/sale_sin_iva_views.xml",
        "views/purchase_sin_iva_views.xml",
        "report/sin_iva_reports.xml",
        "report/templates/report_saleorder_siniva.xml",
        "report/templates/report_purchaseorder_siniva.xml"
    ],
    "installable": true,
    "application": false
}