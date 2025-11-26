from odoo import api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    is_warranty = fields.Boolean(string="Solicitud de garantía", default=False)
    no_order_found = fields.Boolean(string="No encontré mi número de orden", default=False)

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
    """When the sale order is manually chosen on the ticket (Garantía tab),
    just clear the product if no sale order is set. The product field itself
    is free so the agent can choose any product."""
    for ticket in self:
        if not ticket.sale_order_id:
            ticket.product_id = False


