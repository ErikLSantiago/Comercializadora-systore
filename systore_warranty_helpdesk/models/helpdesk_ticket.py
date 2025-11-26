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
    # Campo original usado por el flujo del portal (no se elimina para no romper la lógica)
    product_id = fields.Many2one(
        "product.product",
        string="Producto (portal)",
        help="Producto seleccionado desde la solicitud de portal de garantías.",
    )
    # Nuevo campo libre para que el agente seleccione cualquier producto del catálogo
    warranty_order_product_id = fields.Many2one(
        "product.product",
        string="Productos de la orden",
        help="Producto relacionado con la solicitud de garantía.",
    )

    imei = fields.Char(string="IMEI / Número de serie")
    purchase_date = fields.Date(string="Fecha de compra")
    failure_type = fields.Selection(
        [
            ("fabrication", "Falla de fabricación"),
            ("handling", "Manejo inadecuado"),
            ("other", "Otro"),
        ],
        string="Tipo de falla",
    )
    failure_type_other = fields.Char(string="Otro tipo de falla")
    failure_description = fields.Text(string="Descripción de la falla")

    @api.onchange("sale_order_id")
    def _onchange_sale_order_id(self):
        """Cuando se selecciona manualmente una orden de venta en la pestaña Garantía,
        simplemente limpiamos el producto del portal si se borra la orden.
        El nuevo campo 'Productos de la orden' es libre y no depende de la orden.
        """
        for ticket in self:
            if not ticket.sale_order_id:
                ticket.product_id = False
