from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    x_exchange_rate = fields.Float(
        string="Tipo de cambio (TC)",
        digits=(16, 4),
        default=0.0,
        help="Tipo de cambio USD→MXN utilizado para convertir costos capturados en USD a MXN.",
    )

    x_supplier_bill_id = fields.Many2one(
        "account.move",
        string="Factura Proveedor",
        readonly=True,
        copy=False,
    )
    x_shipping_bill_id = fields.Many2one(
        "account.move",
        string="Factura Envío",
        readonly=True,
        copy=False,
    )
    x_import_bill_id = fields.Many2one(
        "account.move",
        string="Factura Importación",
        readonly=True,
        copy=False,
    )

    x_cost_bills_count = fields.Integer(
        string="Facturas de costos",
        compute="_compute_x_cost_bills_count",
    )

    @api.depends("x_supplier_bill_id", "x_shipping_bill_id", "x_import_bill_id")
    def _compute_x_cost_bills_count(self):
        for order in self:
            order.x_cost_bills_count = sum(bool(x) for x in [order.x_supplier_bill_id, order.x_shipping_bill_id, order.x_import_bill_id])

    def action_recostear(self):
        """Impacta el costo unitario calculado (MXN) a price_unit nativo."""
        for order in self:
            # Permitimos recostear incluso con mercancía recibida (según el flujo del usuario)
            # y en la práctica pueden ajustar el TC varias veces.
            if order.state == "cancel":
                raise UserError(_("No puedes recostear una orden cancelada."))

            if order.x_exchange_rate <= 0:
                raise UserError(_("El tipo de cambio debe ser mayor a 0 para poder recostear."))

            for line in order.order_line:
                if line.display_type:
                    continue
                line.price_unit = line.x_calc_price_mxn or 0.0

        return True

    # -------------------------------------------------------------------------
    # Facturación separada (Opción 1): Proveedor / Envío / Importación
    # -------------------------------------------------------------------------
    def action_generate_cost_bills(self):
        """Genera 3 facturas (borrador): proveedor (por línea), envío (agregada) e importación (agregada).

        Nota: este flujo NO busca afectar inventario ni el invoice_status nativo del PO.
        """
        self.ensure_one()

        if self.state == "cancel":
            raise UserError(_("No puedes generar facturas para una orden cancelada."))

        if self.x_supplier_bill_id or self.x_shipping_bill_id or self.x_import_bill_id:
            raise UserError(_("Ya existen facturas de costos generadas para esta orden. Revisa el botón 'Facturas de costos'."))

        company = self.company_id
        if not company.x_vendor_shipping_id:
            raise UserError(_("Configura el 'Vendor Envío' en Ajustes antes de generar la factura de envío."))
        if not company.x_vendor_import_id:
            raise UserError(_("Configura el 'Vendor Importación' en Ajustes antes de generar la factura de importación."))
        if not company.x_product_shipping_id:
            raise UserError(_("Configura el 'Producto de servicio Envío' en Ajustes antes de generar la factura de envío."))
        if not company.x_product_import_id:
            raise UserError(_("Configura el 'Producto de servicio Importación' en Ajustes antes de generar la factura de importación."))

        # Totales agregados (MXN)
        shipping_total = 0.0
        import_total = 0.0
        supplier_lines = []

        for line in self.order_line:
            if line.display_type:
                continue
            qty = line.product_qty or 0.0
            if qty <= 0:
                continue

            # Proveedor: por producto, solo el costo base (MXN Cost unitario)
            supplier_lines.append((0, 0, {
                "product_id": line.product_id.id,
                "name": line.name or line.product_id.display_name,
                "quantity": qty,
                "price_unit": line.x_gross_mxn or 0.0,
                "tax_ids": [(6, 0, line.taxes_id.ids)] if line.taxes_id else [],
            }))

            shipping_total += qty * (line.x_ship_mxn or 0.0)
            import_total += qty * (line.x_import_mxn or 0.0)

        if not supplier_lines:
            raise UserError(_("No hay líneas facturables en la orden."))

        Move = self.env["account.move"].with_context(default_move_type="in_invoice")
        today = fields.Date.context_today(self)

        # 1) Factura Proveedor (por línea)
        supplier_bill = Move.create({
            "move_type": "in_invoice",
            "partner_id": self.partner_id.id,
            "invoice_date": today,
            "currency_id": self.currency_id.id,
            "invoice_origin": self.name,
            "ref": self.name,
            "invoice_line_ids": supplier_lines,
        })

        # 2) Factura Envío (agregada)
        shipping_product = company.x_product_shipping_id
        shipping_bill = Move.create({
            "move_type": "in_invoice",
            "partner_id": company.x_vendor_shipping_id.id,
            "invoice_date": today,
            "currency_id": self.currency_id.id,
            "invoice_origin": self.name,
            "ref": self.name,
            "invoice_line_ids": [(0, 0, {
                "product_id": shipping_product.id,
                "name": _("Shipping - %s") % (self.name,),
                "quantity": 1.0,
                "price_unit": shipping_total,
                "tax_ids": [(6, 0, shipping_product.supplier_taxes_id.ids)] if shipping_product.supplier_taxes_id else [],
            })],
        })

        # 3) Factura Importación (agregada)
        import_product = company.x_product_import_id
        import_bill = Move.create({
            "move_type": "in_invoice",
            "partner_id": company.x_vendor_import_id.id,
            "invoice_date": today,
            "currency_id": self.currency_id.id,
            "invoice_origin": self.name,
            "ref": self.name,
            "invoice_line_ids": [(0, 0, {
                "product_id": import_product.id,
                "name": _("Import - %s") % (self.name,),
                "quantity": 1.0,
                "price_unit": import_total,
                "tax_ids": [(6, 0, import_product.supplier_taxes_id.ids)] if import_product.supplier_taxes_id else [],
            })],
        })

        self.write({
            "x_supplier_bill_id": supplier_bill.id,
            "x_shipping_bill_id": shipping_bill.id,
            "x_import_bill_id": import_bill.id,
        })

        return self.action_view_cost_bills()

    def action_view_cost_bills(self):
        self.ensure_one()
        bills = (self.x_supplier_bill_id | self.x_shipping_bill_id | self.x_import_bill_id)
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_in_invoice_type")
        action["domain"] = [("id", "in", bills.ids)]
        if len(bills) == 1:
            action["views"] = [(False, "form")]
            action["res_id"] = bills.id
        return action
