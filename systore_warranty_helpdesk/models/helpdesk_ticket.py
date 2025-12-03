from odoo import models, fields, api


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    is_warranty = fields.Boolean(string="Solicitud de garantía", default=False)

    no_order_found = fields.Boolean(
        string="Sin orden encontrada",
        help="Indica si no se encontró una orden de venta asociada en la búsqueda.",
    )

    manual_order_number = fields.Char(
        string="Número de orden (manual)",
        help="Número de orden capturado manualmente en versiones anteriores del formulario.",
    )

    manual_product_description = fields.Char(
        string="Descripción de producto (manual)",
        help="Descripción del producto capturada manualmente en versiones anteriores del formulario.",
    )

    # Campos heredados de Studio, definidos aquí para poder usarlos en vistas y plantillas
    # incluso en bases donde aún no existan desde Studio.
    x_studio_nmero_de_orden_mkp = fields.Char(
        string="Orden de venta (Studio)",
        help="Número de orden de venta proveniente de personalización Studio.",
    )
    x_studio_fecha_orden_producteca = fields.Date(
        string="Fecha de venta (Studio)",
        help="Fecha de venta proveniente de personalización Studio.",
    )
    x_studio_canal_de_venta_1 = fields.Char(
        string="Canal de venta (Studio)",
        help="Canal de venta proveniente de personalización Studio.",
    )

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Orden de venta",
        help="Orden de venta asociada a la garantía.",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        help="Producto asociado automáticamente desde la solicitud de garantías.",
    )

    product_reported_id = fields.Many2one(
        "product.product",
        string="Producto reportado",
        help="Producto reportado en la garantía.",
    )


    warranty_phone = fields.Char(
        string="Teléfono (garantía)",
        help="Teléfono de contacto proporcionado en la solicitud de garantía.",
    )


    warranty_imei = fields.Char(
        string="IMEI / Serie (garantía)",
        help="IMEI o número de serie capturado en la solicitud de garantía.",
    )


    failure_type = fields.Selection(
        [
            ("pantalla", "Pantalla"),
            ("no_enciende", "No enciende"),
            ("carga", "Carga"),
            ("otro", "Otro (especifique)"),
        ],
        string="Tipo de falla",
        help="Tipo de falla reportada en la solicitud de garantía desde el formulario web.",
    )

    failure_type_other = fields.Char(
        string="Otro tipo de falla",
        help="Descripción libre del tipo de falla cuando se selecciona una opción personalizada.",
    )

    failure_description = fields.Text(
        string="Descripción de la falla",
        help="Descripción detallada de la falla reportada en la solicitud de garantía.",
    )

    warranty_tracking_number = fields.Char(
        string="Número de guía (manual)",
        help="Número de guía de la paquetería relacionado con el envío de la garantía.",
    )
    warranty_carrier_name = fields.Char(
        string="Paquetera (manual)",
        help="Nombre de la paquetería utilizada para el envío de la garantía.",
    )
    warranty_account_number = fields.Char(
        string="Número de cuenta (manual)",
        help="Número de cuenta o identificador asociado a la paquetería.",
    )



    @api.onchange("sale_order_id")
    def _onchange_sale_order_id_sync_header_fields(self):
        """Cuando se selecciona una orden de venta en la pestaña Garantía,
        copiar al encabezado los campos de Studio si existen en la orden.

        - x_studio_canal_de_venta_1
        - x_studio_nmero_de_orden_mkp
        - x_studio_fecha_orden_producteca
        """
        for ticket in self:
            sale_order = ticket.sale_order_id
            if not sale_order:
                continue

            # Copiar canal de venta
            if (
                "x_studio_canal_de_venta_1" in sale_order._fields
                and "x_studio_canal_de_venta_1" in ticket._fields
            ):
                ticket.x_studio_canal_de_venta_1 = sale_order.x_studio_canal_de_venta_1.display_name

            # Copiar número de orden MKP
            if (
                "x_studio_nmero_de_orden_mkp" in sale_order._fields
                and "x_studio_nmero_de_orden_mkp" in ticket._fields
            ):
                ticket.x_studio_nmero_de_orden_mkp = sale_order.x_studio_nmero_de_orden_mkp

            # Copiar fecha de venta Producteca
            if (
                "x_studio_fecha_orden_producteca" in sale_order._fields
                and "x_studio_fecha_orden_producteca" in ticket._fields
            ):
                ticket.x_studio_fecha_orden_producteca = sale_order.x_studio_fecha_orden_producteca


    def rename_ticket_with_order_and_product(self):
        """Renombra el ticket usando:
            - Nombre original del ticket
            - Número de orden de venta (si existe)
            - Nombre del producto (si existe)

            Formato:
                NombreOriginal - Orden - Producto
        """
        for ticket in self:
            base_name = ticket.name or ""
            order_name = ticket.sale_order_id.name or ""
            if hasattr(ticket, "product_reported_id") and ticket.product_reported_id:
                product_name = ticket.product_reported_id.display_name
            else:
                product_name = (
                    ticket.product_id.display_name
                    if getattr(ticket, "product_id", False) and ticket.product_id
                    else ""
                )

            parts = [p for p in [base_name, order_name, product_name] if p]
            ticket.name = " - ".join(parts)
        return True

    def action_update_ticket_name(self):
        """Acción llamada desde el botón 'Actualizar ticket' en la vista.

        Simplemente delega en rename_ticket_with_order_and_product.
        """
        self.rename_ticket_with_order_and_product()
        return True
