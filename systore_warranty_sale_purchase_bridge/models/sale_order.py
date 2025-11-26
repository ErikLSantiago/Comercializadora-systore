
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    warranty_ticket_ids = fields.One2many(
        "helpdesk.ticket",
        "sale_order_id",
        string="Tickets de garantía",
        help="Tickets de garantía ligados a esta orden de venta.",
        readonly=True,
    )

    def action_create_warranty_purchase_scrap(self):
        """Crear una orden de compra en la empresa 'Scrap Systore'
        a partir de esta orden de venta.

        - Usa como proveedor la Dirección de factura (partner_invoice_id).
        - Copia solo las líneas de producto ALMACENABLE (tipo 'product').
        - Usa como nombre de la OC el número de la OV.
        - Usa como origin el nombre de la OV + nombres de tickets (si existen).
        """
        self.ensure_one()

        target_company = self.env["res.company"].search(
            [("name", "=", "Scrap Systore")], limit=1
        )
        if not target_company:
            raise UserError(
                _(
                    "No se encontró la empresa 'Scrap Systore'. "
                    "Crea la empresa o ajusta el nombre en el módulo bridge."
                )
            )

        PurchaseOrder = self.env["purchase.order"].with_company(target_company).sudo()

        ticket_names = ", ".join(self.warranty_ticket_ids.mapped("name")) or ""
        origin = self.name
        if ticket_names:
            origin = f"{self.name} - {ticket_names}"

        line_vals = []
        for line in self.order_line:
            # Ignorar líneas sin producto o decorativas
            if not line.product_id or line.display_type:
                continue

            # Tomar solo productos ALMACENABLES
            detailed_type = getattr(line.product_id, "detailed_type", False) or getattr(line.product_id, "type", False)
            if detailed_type != "product":
                continue

            line_vals.append(
                (
                    0,
                    0,
                    {
                        "name": line.name or line.product_id.display_name,
                        "product_id": line.product_id.id,
                        "product_qty": line.product_uom_qty,
                        "product_uom": line.product_uom.id,
                        "price_unit": line.price_unit,
                        "date_planned": fields.Datetime.now(),
                    },
                )
            )

        if not line_vals:
            raise UserError(
                _(
                    "La orden de venta no tiene líneas de producto almacenable "
                    "para generar la compra."
                )
            )

        # Proveedor = Dirección de factura; si no existe, usar partner de la OV
        supplier = self.partner_invoice_id or self.partner_id

        po_vals = {
            "name": self.name,  # nombre de la OC = número/nombre de la OV
            "partner_id": supplier.id,
            "company_id": target_company.id,
            "origin": origin,
            "order_line": line_vals,
        }

        purchase = PurchaseOrder.create(po_vals)

        # Mensaje en el chatter de la OV
        message = _(
            "Orden de compra de garantía creada en %s: "
            "<a href='#' data-oe-model='purchase.order' data-oe-id='%d'>%s</a>"
        ) % (target_company.display_name, purchase.id, purchase.name)
        self.message_post(body=message)

        # Abrir la orden de compra creada
        action = self.env.ref("purchase.purchase_form_action").read()[0]
        action["views"] = [(self.env.ref("purchase.purchase_order_form").id, "form")]
        action["res_id"] = purchase.id
        return action
