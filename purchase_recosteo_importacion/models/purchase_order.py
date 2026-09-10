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

    x_shipping_vendor_id = fields.Many2one(
        "res.partner",
        string="Proveedor logístico",
        default=lambda self: self.env.company.x_vendor_shipping_id,
        check_company=True,
        help="Proveedor al que se emitirá la factura agregada de envío para esta orden.",
    )
    x_import_vendor_id = fields.Many2one(
        "res.partner",
        string="Proveedor de importación",
        default=lambda self: self.env.company.x_vendor_import_id,
        check_company=True,
        help="Proveedor al que se emitirá la factura agregada de importación para esta orden.",
    )

    @api.onchange("company_id")
    def _onchange_company_id_cost_bill_vendors(self):
        for order in self:
            if order.company_id:
                order.x_shipping_vendor_id = order.company_id.x_vendor_shipping_id
                order.x_import_vendor_id = order.company_id.x_vendor_import_id

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
        """Impacta el costo unitario calculado (MXN) a price_unit nativo.

        Si ya existen las facturas de costos generadas por este módulo, también
        sincroniza únicamente las que continúen en borrador. Las facturas ya
        confirmadas o canceladas se conservan sin cambios y no bloquean el recosteo.
        """
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

            order._sync_cost_bills_after_recosteo()

        return True

    def _get_cost_bill_amounts_and_lines(self):
        """Prepara las líneas y totales actuales para las 3 facturas de costos."""
        self.ensure_one()
        supplier_lines = []
        shipping_total = 0.0
        import_total = 0.0

        for line in self.order_line:
            if line.display_type:
                continue

            qty = line.product_qty or 0.0
            if qty <= 0:
                continue

            supplier_lines.append((0, 0, {
                "product_id": line.product_id.id,
                "name": line.name or line.product_id.display_name,
                "quantity": qty,
                "price_unit": line.x_gross_mxn or 0.0,
                "tax_ids": [(6, 0, line.taxes_id.ids)] if line.taxes_id else [],
            }))

            shipping_total += qty * (line.x_ship_mxn or 0.0)
            import_total += qty * (line.x_import_mxn or 0.0)

        return supplier_lines, shipping_total, import_total

    def _prepare_single_service_invoice_line(self, product, name, amount):
        self.ensure_one()
        return (0, 0, {
            "product_id": product.id,
            "name": name,
            "quantity": 1.0,
            "price_unit": amount,
            "tax_ids": [(6, 0, product.supplier_taxes_id.ids)] if product.supplier_taxes_id else [],
        })

    def _ensure_cost_bill_can_be_reposted(self, bill):
        """Valida que una factura publicada pueda ser reabierta de forma segura."""
        if not bill or bill.state != "posted":
            return

        # Si existen pagos o conciliaciones, Odoo normalmente no permite regresar a borrador
        # sin romper trazabilidad contable. En ese caso detenemos el recosteo con un mensaje claro.
        if bill.payment_state in ("paid", "in_payment", "partial"):
            raise UserError(_(
                "La factura %(bill)s ya tiene pagos o conciliaciones (%(state)s). "
                "No puede regresarse automáticamente a borrador para recostearse."
            ) % {
                "bill": bill.display_name,
                "state": bill.payment_state,
            })

    def _rewrite_cost_bill_lines(self, bill, invoice_line_commands):
        """Reemplaza las líneas de factura por los importes recalculados."""
        bill.invoice_line_ids.unlink()
        bill.write({"invoice_line_ids": invoice_line_commands})

    def _update_cost_bill(self, bill, invoice_line_commands):
        """Actualiza únicamente las facturas de costo que continúen en borrador.

        Una factura confirmada o cancelada se mantiene intacta. Esto permite que
        las otras facturas del conjunto que aún estén en borrador sí se actualicen
        durante el recosteo, sin intentar reabrir documentos contables publicados.
        """
        if not bill or bill.state != "draft":
            return

        self._rewrite_cost_bill_lines(bill, invoice_line_commands)

    def _sync_cost_bills_after_recosteo(self):
        """Sincroniza las facturas de costos que aún estén en borrador tras recostear."""
        for order in self:
            bills = order.x_supplier_bill_id | order.x_shipping_bill_id | order.x_import_bill_id
            if not bills:
                continue

            company = order.company_id
            if order.x_shipping_bill_id and not company.x_product_shipping_id:
                raise UserError(_("Configura el 'Producto de servicio Envío' en Ajustes antes de actualizar la factura de envío."))
            if order.x_import_bill_id and not company.x_product_import_id:
                raise UserError(_("Configura el 'Producto de servicio Importación' en Ajustes antes de actualizar la factura de importación."))

            supplier_lines, shipping_total, import_total = order._get_cost_bill_amounts_and_lines()
            if order.x_supplier_bill_id and not supplier_lines:
                raise UserError(_("No hay líneas facturables en la orden para actualizar la factura de proveedor."))

            if order.x_supplier_bill_id:
                order._update_cost_bill(order.x_supplier_bill_id, supplier_lines)

            if order.x_shipping_bill_id:
                shipping_line = [order._prepare_single_service_invoice_line(
                    company.x_product_shipping_id,
                    _("Shipping - %s") % (order.name,),
                    shipping_total,
                )]
                order._update_cost_bill(order.x_shipping_bill_id, shipping_line)

            if order.x_import_bill_id:
                import_line = [order._prepare_single_service_invoice_line(
                    company.x_product_import_id,
                    _("Import - %s") % (order.name,),
                    import_total,
                )]
                order._update_cost_bill(order.x_import_bill_id, import_line)

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
        if not self.x_shipping_vendor_id:
            raise UserError(_("Selecciona el 'Proveedor logístico' en la orden antes de generar la factura de envío."))
        if not self.x_import_vendor_id:
            raise UserError(_("Selecciona el 'Proveedor de importación' en la orden antes de generar la factura de importación."))
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
            "partner_id": self.x_shipping_vendor_id.id,
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
            "partner_id": self.x_import_vendor_id.id,
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
