from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    x_vendor_shipping_id = fields.Many2one(
        "res.partner",
        string="Proveedor logístico",
        help="Proveedor logístico predeterminado para las nuevas órdenes de compra. Puede cambiarse en cada orden antes de generar las facturas.",
    )
    x_vendor_import_id = fields.Many2one(
        "res.partner",
        string="Proveedor de importación",
        help="Proveedor de importación predeterminado para las nuevas órdenes de compra. Puede cambiarse en cada orden antes de generar las facturas.",
    )

    x_product_shipping_id = fields.Many2one(
        "product.product",
        string="Producto de servicio Envío",
        domain=[("type", "=", "service")],
        help="Producto de servicio que se usará en la factura agregada de envío (para definir cuentas/impuestos).",
    )
    x_product_import_id = fields.Many2one(
        "product.product",
        string="Producto de servicio Importación",
        domain=[("type", "=", "service")],
        help="Producto de servicio que se usará en la factura agregada de importación (para definir cuentas/impuestos).",
    )
