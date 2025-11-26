from odoo import api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    is_warranty = fields.Boolean(string="Solicitud de garantía", default=False)

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Orden de venta",
        help="Orden de venta asociada a la garantía.",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        help="Producto reportado en la garantía.",
    )

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id_set_product_domain(self):
        """Limit available products to those present in the selected sale order."""
        if self.sale_order_id:
            products = self.sale_order_id.order_line.product_id
            return {'domain': {'product_id': [('id', 'in', products.ids)]}}
        return {'domain': {'product_id': []}}

    no_order_found = fields.Boolean(string="No encontró su número de orden")
    manual_order_number = fields.Char(
        string="Número de orden (manual)",
        help="Número de orden proporcionado manualmente por el cliente.",
    )
    manual_product_description = fields.Char(
        string="Descripción de producto (manual)",
        help="Descripción del producto cuando el cliente no encontró su orden.",
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

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        """Limit the Product field to the products of the selected sale order
        when the sale order is manually chosen on the ticket (Garantía tab).
        """
        for ticket in self:
            if not ticket.sale_order_id:
                ticket.product_id = False
                return {'domain': {'product_id': []}}

            product_ids = ticket.sale_order_id.order_line.mapped('product_id').ids
            # Restrict the product selection to the products from the sale order
            return {'domain': {'product_id': [('id', 'in', product_ids)]}}
