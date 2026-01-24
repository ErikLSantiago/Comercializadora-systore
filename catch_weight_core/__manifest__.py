{
    "name": "Catch Weight Core (MRP/Stock)",
    "version": "19.0.1.0.0",
    "category": "Manufacturing",
    "summary": "Catch-weight production by lot (SKU-weight-date), weight balance & FIFO costing by weight, waste by-product, lot labels.",
    "depends": ["mrp", "stock", "product", "stock_account"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/product_views.xml",
        "views/stock_lot_views.xml",
        "views/mrp_views.xml",
        "reports/lot_label.xml",
        "reports/lot_label_template.xml",
        "wizards/mrp_cw_finish_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
