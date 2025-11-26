from odoo import models, fields, api


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    # Indicador de que el ticket proviene del flujo de garantías
    is_warranty = fields.Boolean(string="Solicitud de garantía", default=False)

    # Orden de venta asociada al ticket de garantía
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Orden de venta",
        help="Orden de venta asociada a la garantía.",
    )

    # Productos disponibles en la orden de venta para seleccionar en la garantía
    warranty_sale_product_ids = fields.Many2many(
        "product.product",
        string="Productos de la orden de venta",
        compute="_compute_warranty_sale_product_ids",
        help="Lista de productos disponibles en la orden de venta seleccionada.",
    )

    # Producto de la orden de venta elegido para esta garantía
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        domain="[('id', 'in', warranty_sale_product_ids)]",
        help="Producto de la orden de venta asociado a la garantía.",
    )

    warranty_phone = fields.Char(string="Teléfono de contacto")
    warranty_imei = fields.Char(string="Número de serie / IMEI")

    failure_type = fields.Selection(
        [
            ("pantalla", "Pantalla"),
            ("no_enciende", "No enciende"),
            ("carga", "Carga"),
            ("otro", "Otro (especifique)"),
        ],
        string="Tipo de falla",
    )
    failure_type_other = fields.Char(string="Otro tipo de falla")
    failure_description = fields.Text(string="Descripción de la falla")

    @api.depends("sale_order_id")
    def _compute_warranty_sale_product_ids(self):
        """Limita los productos disponibles al dominio de la orden de venta seleccionada."""
        for ticket in self:
            if ticket.sale_order_id:
                ticket.warranty_sale_product_ids = ticket.sale_order_id.order_line.mapped("product_id")
            else:
                ticket.warranty_sale_product_ids = False