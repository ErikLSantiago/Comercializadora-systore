# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


class SaleOrder(models.Model):
    _inherit = "sale.order"

    mkp_parent_order_ref = fields.Char(
        string="Orden padre",
        copy=False,
        index=True,
        help=(
            "Número de la operación padre informado por el sistema externo. "
            "La orden padre no se crea como orden de venta en Odoo."
        ),
    )
    mkp_parent_order_id = fields.Many2one(
        "sale.order",
        string="Orden padre anterior",
        copy=False,
        readonly=True,
        help="Campo técnico conservado únicamente para migrar datos de la versión anterior.",
    )
    mkp_delivery_state = fields.Selection(
        [
            ("none", "Sin órdenes seller"),
            ("pending", "Pendiente"),
            ("partial", "Parcialmente entregada"),
            ("done", "Entrega completa"),
            ("cancel", "Cancelada"),
        ],
        string="Estado de entrega seller",
        compute="_compute_mkp_delivery_state",
        store=False,
    )
    mkp_consolidated_invoice_ids = fields.Many2many(
        "account.move",
        "mkp_sale_parent_invoice_rel",
        "sale_order_id",
        "move_id",
        string="Facturas consolidadas",
        copy=False,
        readonly=True,
    )

    order_status = fields.Char(string="Estado de la orden")
    external_order_ref = fields.Char(string="External Order Ref", help="Referencia externa (VTEX/Marketplace).")
    # --- NUEVO: mostrar facturas debajo de líneas ---
    mkp_customer_invoice_id = fields.Many2one(
        "account.move",
        string="Factura cliente",
        compute="_compute_mkp_invoices",
        readonly=True,
    )
    mkp_vendor_bill_id = fields.Many2one(
        "account.move",
        string="Factura proveedor",
        compute="_compute_mkp_invoices",
        readonly=True,
    )

    mkp_purchase_order_id = fields.Many2one(
        "purchase.order",
        string="Orden de compra asociada",
        compute="_compute_mkp_invoices",
        readonly=True,
    )

    def init(self):
        super().init()
        self.env.cr.execute(
            """
            UPDATE sale_order AS child
               SET mkp_parent_order_ref = parent.name
              FROM sale_order AS parent
             WHERE child.mkp_parent_order_id = parent.id
               AND COALESCE(child.mkp_parent_order_ref, '') = ''
            """
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "mkp_parent_order_ref" in vals:
                vals["mkp_parent_order_ref"] = (
                    (vals.get("mkp_parent_order_ref") or "").strip() or False
                )
        return super().create(vals_list)

    def write(self, vals):
        if "mkp_parent_order_ref" in vals:
            vals["mkp_parent_order_ref"] = (
                (vals.get("mkp_parent_order_ref") or "").strip() or False
            )
        return super().write(vals)

    def _mkp_get_seller(self):
        """Return the seller already informed by the client's integration.

        The Studio field is the active source.  The additional name is accepted
        only as a compatibility fallback for databases where the same field was
        created without the Studio prefix.
        """
        self.ensure_one()
        for field_name in (
            "x_studio_dropshipping_seller_id",
            "dropshipping_seller_id",
        ):
            if field_name not in self._fields:
                continue
            seller = self[field_name]
            if not seller:
                continue
            if getattr(seller, "_name", False) == "res.partner":
                return seller
            if isinstance(seller, int):
                return self.env["res.partner"].browse(seller).exists()
            if isinstance(seller, str) and seller.isdigit():
                return self.env["res.partner"].browse(int(seller)).exists()
        return self.env["res.partner"]

    def _mkp_get_line_seller_cost(self, line):
        if "x_seller_cost" not in line._fields:
            raise ValidationError(
                "No existe el campo técnico x_seller_cost en las líneas de venta. "
                "Verifica que la personalización que informa el costo del seller esté instalada."
            )
        return line.x_seller_cost or 0.0

    @api.depends(
        "invoice_ids",
        "mkp_consolidated_invoice_ids",
        "mkp_parent_order_ref",
        "company_id",
    )
    def _compute_mkp_invoices(self):
        for so in self:
            # Factura cliente (última no cancelada)
            siblings = so._mkp_get_sibling_orders()
            customer = (
                so.invoice_ids
                | siblings.mapped("invoice_ids")
                | siblings.mapped("mkp_consolidated_invoice_ids")
            ).filtered(
                lambda m: m.move_type in ("out_invoice", "out_refund") and m.state != "cancel"
            )
            so.mkp_customer_invoice_id = customer.sorted(lambda m: m.id)[-1] if customer else False

            # Factura proveedor (última no cancelada de la PO relacionada)
            bill = False
            po = so._mkp_get_related_po()
            so.mkp_purchase_order_id = po or False
            if po:
                vendor_moves = po.invoice_ids.filtered(
                    lambda m: m.move_type in ("in_invoice", "in_refund") and m.state != "cancel"
                )
                bill = vendor_moves.sorted(lambda m: m.id)[-1] if vendor_moves else False
            so.mkp_vendor_bill_id = bill

    @api.depends(
        "mkp_parent_order_ref",
        "picking_ids.state",
    )
    def _compute_mkp_delivery_state(self):
        for order in self:
            siblings = order._mkp_get_sibling_orders()
            if not siblings:
                order.mkp_delivery_state = "none"
                continue
            if all(sibling.state == "cancel" for sibling in siblings):
                order.mkp_delivery_state = "cancel"
                continue
            states = [
                sibling._mkp_is_fully_delivered()
                for sibling in siblings
                if sibling.state != "cancel"
            ]
            if states and all(states):
                order.mkp_delivery_state = "done"
            elif any(states):
                order.mkp_delivery_state = "partial"
            else:
                order.mkp_delivery_state = "pending"

    # ---------------------------------------------------------------------
    # Core flow hooks
    # ---------------------------------------------------------------------
    def action_confirm(self):
        for order in self:
            if order.mkp_parent_order_ref:
                siblings = order._mkp_get_sibling_orders()
                existing_invoices = siblings.mapped(
                    "mkp_consolidated_invoice_ids"
                ).filtered(
                    lambda move: move.move_type == "out_invoice"
                    and move.state != "cancel"
                )
                if existing_invoices:
                    raise ValidationError(
                        "No es posible confirmar la orden %s porque la Orden padre "
                        "%s ya tiene una factura consolidada activa: %s."
                        % (
                            order.display_name,
                            order.mkp_parent_order_ref,
                            ", ".join(existing_invoices.mapped("display_name")),
                        )
                    )
            order._mkp_validate_seller_required()
        res = super().action_confirm()
        for order in self:
            order._mkp_create_and_confirm_settlement_po()
        return res

    def action_cancel(self):
        res = super().action_cancel()
        for order in self:
            order._mkp_cancel_related_pos()
        return res

    # ---------------------------------------------------------------------
    # Consolidated customer invoicing
    # ---------------------------------------------------------------------
    def _create_invoices(self, grouped=False, final=False, date=None):
        grouped_orders = self.filtered("mkp_parent_order_ref")
        if grouped_orders and not self.env.context.get("mkp_consolidated_invoice"):
            parent_refs = set(grouped_orders.mapped("mkp_parent_order_ref"))
            if len(parent_refs) != 1 or len(grouped_orders) != len(self):
                raise UserError(
                    "La facturación consolidada debe ejecutarse para un solo número de "
                    "Orden padre a la vez."
                )
            return grouped_orders[0]._mkp_create_consolidated_invoice_moves(
                grouped=grouped,
                final=final,
                date=date,
            )
        return super()._create_invoices(grouped=grouped, final=final, date=date)

    def action_mkp_create_consolidated_invoice(self):
        self.ensure_one()
        moves = self._mkp_create_consolidated_invoice_moves()
        customer_moves = moves.filtered(lambda move: move.move_type == "out_invoice")
        invoice = customer_moves.sorted(lambda move: move.id)[-1:] or False
        if not invoice:
            raise UserError("No se encontró una factura consolidada para esta operación.")
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": invoice.id,
        }

    def _mkp_get_sibling_orders(self):
        self.ensure_one()
        if not self.mkp_parent_order_ref:
            return self
        return self.search(
            [
                ("mkp_parent_order_ref", "=", self.mkp_parent_order_ref),
                ("company_id", "=", self.company_id.id),
            ],
            order="id",
        )

    def _mkp_create_consolidated_invoice_moves(
        self, grouped=False, final=False, date=None
    ):
        self.ensure_one()
        parent_ref = (self.mkp_parent_order_ref or "").strip()
        if not parent_ref:
            raise UserError(
                "Captura el número de Orden padre antes de crear la factura consolidada."
            )
        siblings = self._mkp_get_sibling_orders()

        # Una factura que será timbrada debe ser definitiva. Cada hija tiene que
        # haber terminado su operación: entrega completa o cancelación total.
        unfinished = siblings.filtered(
            lambda order: order.state != "cancel"
            and not order._mkp_is_fully_delivered()
        )
        if unfinished:
            raise UserError(
                "No es posible facturar la Orden padre %s porque estas órdenes hijas "
                "todavía no están completamente entregadas ni canceladas: %s. "
                "Entrega completamente cada orden o cancela las que no serán surtidas "
                "antes de emitir y timbrar la factura."
                % (parent_ref, ", ".join(unfinished.mapped("name")))
            )

        # Las canceladas alcanzaron estado terminal, pero nunca deben aportar
        # líneas a la factura consolidada.
        children = siblings.filtered(
            lambda order: order.state in ("sale", "done")
            and order._mkp_is_fully_delivered()
        )
        if not children:
            raise UserError(
                "La Orden padre %s no tiene órdenes hijas entregadas para facturar; "
                "todas están canceladas." % parent_ref
            )

        reference = children[0]
        if any(child.partner_invoice_id != reference.partner_invoice_id for child in children):
            raise UserError("Todas las órdenes seller deben tener el mismo contacto de facturación.")
        if any(child.partner_id != reference.partner_id for child in children):
            raise UserError("Todas las órdenes seller deben pertenecer al mismo cliente.")
        if any(child.company_id != reference.company_id for child in children):
            raise UserError("Todas las órdenes seller deben pertenecer a la misma compañía.")
        if any(child.currency_id != reference.currency_id for child in children):
            raise UserError("Todas las órdenes seller deben usar la misma moneda.")
        if any(child.fiscal_position_id != reference.fiscal_position_id for child in children):
            raise UserError("Todas las órdenes seller deben usar la misma posición fiscal.")
        if any(child.payment_term_id != reference.payment_term_id for child in children):
            raise UserError("Todas las órdenes seller deben usar el mismo plazo de pago.")

        existing = siblings.mapped("mkp_consolidated_invoice_ids").filtered(
            lambda move: move.move_type == "out_invoice" and move.state != "cancel"
        )
        invoiceable_lines = children.mapped("order_line").filtered(
            lambda line: not line.display_type and line.qty_to_invoice > 0
        )
        if existing:
            if invoiceable_lines:
                raise UserError(
                    "La Orden padre %s ya tiene una factura consolidada activa. "
                    "No se pueden añadir líneas ni generar una segunda factura porque "
                    "el comprobante debe permanecer definitivo."
                    % parent_ref
                )
            return existing
        if not invoiceable_lines:
            raise UserError(
                "No hay líneas pendientes de facturar para la Orden padre %s." % parent_ref
            )

        moves = children.with_context(
            mkp_consolidated_invoice=True,
            mkp_parent_order_ref=parent_ref,
        )._create_invoices(grouped=False, final=final, date=date)
        customer_moves = moves.filtered(lambda m: m.move_type == "out_invoice")
        if len(customer_moves) != 1:
            raise UserError(
                "No fue posible generar una sola factura consolidada. Revisa que las órdenes "
                "seller compartan cliente, contacto de facturación, moneda y compañía."
            )
        customer_moves.write({"mkp_parent_order_ref": parent_ref})
        children.write({"mkp_consolidated_invoice_ids": [(4, customer_moves.id)]})
        for child in children:
            child.message_post(
                body="Se creó la factura consolidada <b>%s</b> para la Orden padre "
                "<b>%s</b> con las líneas de: %s."
                % (
                    customer_moves.display_name,
                    parent_ref,
                    ", ".join(children.mapped("name")),
                )
            )
        return customer_moves

    def _mkp_is_fully_delivered(self):
        self.ensure_one()
        lines = self.order_line.filtered(
            lambda line: not line.display_type
            and line.product_id
            and line.product_id.type in ("product", "consu")
            and line.product_uom_qty > 0
        )
        if not lines:
            return False
        return all(
            float_compare(
                line.qty_delivered,
                line.product_uom_qty,
                precision_rounding=line.product_uom.rounding,
            )
            >= 0
            for line in lines
        )

    def _mkp_on_seller_delivery_completed(self):
        """Create and post only this seller's bill once its delivery is complete."""
        self.ensure_one()
        if not self._mkp_get_seller() or not self._mkp_is_fully_delivered():
            return
        self._mkp_post_vendor_bill_linked()

    # ---------- Helpers ----------
    def _mkp_validate_seller_required(self):
        self.ensure_one()
        lines = self.order_line.filtered(
            lambda l: l.product_id
            and l.product_id.type in ("product", "consu")
            and l.product_uom_qty > 0
        )
        seller = self._mkp_get_seller()
        if lines and not seller:
            raise ValidationError(
                "Debes informar el Seller de dropshipping en la Orden de Venta antes de confirmar."
            )
        if seller and not seller.is_seller_managed:
            raise ValidationError(
                f"El contacto '{seller.display_name}' no tiene activado "
                "'Gestionar como Seller'."
            )
        if seller and not seller.seller_location_id:
            raise ValidationError(
                f"El Seller '{seller.display_name}' no tiene una Ubicación del Seller configurada."
            )
        if seller and not seller.seller_in_picking_type_id:
            raise ValidationError(
                f"El Seller '{seller.display_name}' no tiene una Operación de Recepción configurada."
            )
        for line in lines:
            if self._mkp_get_line_seller_cost(line) <= 0:
                raise ValidationError(
                    f"El campo x_seller_cost debe ser mayor a cero para "
                    f"'{line.product_id.display_name}' antes de confirmar."
                )

    def _mkp_get_related_po(self):
        """Retorna la PO asociada a esta SO (flujo 1 PO por SO)."""
        self.ensure_one()
        return self.env["purchase.order"].search(
            [
                ("mkp_sale_order_id", "=", self.id),
                ("mkp_seller_settlement", "=", True),
                ("company_id", "=", self.company_id.id),
                ("state", "!=", "cancel"),
            ],
            order="id desc",
            limit=1,
        )

    def _mkp_create_vendor_bill_for_related_po(self):
        """Crea una Vendor Bill (account.move in_invoice) para la PO asociada (en draft)."""
        self.ensure_one()
        po = self._mkp_get_related_po()
        if not po:
            return

        # Evitar duplicados
        existing = po.invoice_ids.filtered(
            lambda m: m.move_type in ("in_invoice", "in_refund") and m.state != "cancel"
        )
        if existing:
            return

        # La OC debe estar confirmada para documentar la obligación con el seller.
        if po.state in ("draft", "sent", "to approve"):
            self._mkp_confirm_settlement_po(po)

        invoice_vals = po._prepare_invoice()
        invoice_lines = []
        for line in po.order_line.filtered(lambda item: not item.display_type):
            remaining_qty = line.product_qty - line.qty_invoiced
            if float_compare(
                remaining_qty,
                0.0,
                precision_rounding=line.product_uom.rounding,
            ) <= 0:
                continue
            line_vals = line._prepare_account_move_line()
            line_vals["quantity"] = remaining_qty
            invoice_lines.append((0, 0, line_vals))

        if not invoice_lines:
            return

        today = fields.Date.context_today(self)
        invoice_vals.update(
            {
                "invoice_date": today,
                "date": today,
                "invoice_line_ids": invoice_lines,
            }
        )
        bill = (
            self.env["account.move"]
            .with_company(po.company_id)
            .sudo()
            .with_context(default_move_type="in_invoice")
            .create(invoice_vals)
        )
        self.message_post(
            body=f"Se creó automáticamente la factura de proveedor "
            f"<b>{bill.display_name}</b> desde la OC <b>{po.name}</b>."
        )

    def _mkp_post_vendor_bill_linked(self):
        """Publica la Vendor Bill vinculada a esta SO (si existe) o la crea y publica."""
        self.ensure_one()
        po = self._mkp_get_related_po()
        if not po:
            return

        bill = self.mkp_vendor_bill_id
        if not bill:
            # Intentar crearla
            self._mkp_create_vendor_bill_for_related_po()
            bill = po.invoice_ids.filtered(
                lambda m: m.move_type in ("in_invoice", "in_refund") and m.state != "cancel"
            ).sorted(lambda m: m.id)[-1:] or False

        if bill and bill.state == "draft":
            # Publicar con el contexto de la compañía de la bill
            bill = bill.with_company(bill.company_id).sudo()

            # Odoo (y localizaciones) pueden exigir fecha de factura para Vendor Bills.
            # Si no existe, usar la fecha del día en que se está publicando.
            today = fields.Date.context_today(bill)
            vals = {}
            if not bill.invoice_date:
                vals["invoice_date"] = today
            # "date" es la fecha contable; si viene vacía, también la seteamos para evitar validaciones.
            if not bill.date:
                vals["date"] = today
            if vals:
                bill.write(vals)
            bill.action_post()
            self.message_post(body=f"Se publicó automáticamente la Vendor Bill <b>{bill.name or bill.ref or bill.id}</b>.")

    def _mkp_cancel_vendor_bill_linked(self):
        """Cancela la Vendor Bill vinculada a esta SO cuando se cancela la factura del cliente."""
        self.ensure_one()
        bill = self.mkp_vendor_bill_id
        if not bill:
            po = self._mkp_get_related_po()
            if not po:
                return
            vendor_moves = po.invoice_ids.filtered(
                lambda m: m.move_type in ("in_invoice", "in_refund") and m.state != "cancel"
            )
            bill = vendor_moves.sorted(lambda m: m.id)[-1] if vendor_moves else False

        if not bill or bill.state == "cancel":
            return

        bill = bill.with_company(bill.company_id).sudo()
        if bill.state == "posted":
            try:
                bill.button_draft()
            except Exception as e:
                raise ValidationError(
                    f"No fue posible regresar la factura de proveedor {bill.display_name} a borrador antes de cancelarla. Detalle: {e}"
                )

        try:
            bill.button_cancel()
        except Exception as e:
            raise ValidationError(
                f"No fue posible cancelar la factura de proveedor {bill.display_name}. Detalle: {e}"
            )

        self.message_post(body=f"Se canceló automáticamente la Vendor Bill <b>{bill.display_name or bill.name or bill.id}</b>.")

    # ---------------------------------------------------------------------
    # Commercial purchase order for inventory already held by the seller
    # ---------------------------------------------------------------------

    def _mkp_create_and_confirm_settlement_po(self):
        self.ensure_one()
        existing = self._mkp_get_related_po()
        if existing:
            self._mkp_confirm_settlement_po(existing)
            return existing

        seller = self._mkp_get_seller()
        if not seller:
            return self.env["purchase.order"]

        sale_lines = self.order_line.filtered(
            lambda line: not line.display_type
            and line.product_id
            and line.product_id.type in ("product", "consu")
            and line.product_uom_qty > 0
        )
        if not sale_lines:
            return self.env["purchase.order"]

        date_planned = self.commitment_date or fields.Datetime.now()
        order_line_commands = []
        purchase_line_fields = self.env["purchase.order.line"]._fields
        for line in sale_lines:
            line_vals = {
                "product_id": line.product_id.id,
                "name": line.name or line.product_id.display_name,
                "product_qty": line.product_uom_qty,
                "product_uom": line.product_uom.id,
                "price_unit": self._mkp_get_line_seller_cost(line),
                "date_planned": date_planned,
            }
            if "sale_line_id" in purchase_line_fields:
                line_vals["sale_line_id"] = line.id
            order_line_commands.append((0, 0, line_vals))

        po_vals = {
            "partner_id": seller.id,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "origin": self.name,
            "mkp_sale_order_id": self.id,
            "mkp_seller_settlement": True,
            "order_line": order_line_commands,
        }
        if self.external_order_ref:
            po_vals["partner_ref"] = self.external_order_ref

        po = (
            self.env["purchase.order"]
            .with_company(self.company_id)
            .with_context(allowed_company_ids=[self.company_id.id])
            .create(po_vals)
        )
        self._mkp_confirm_settlement_po(po)
        self.message_post(
            body=f"Se creó y confirmó automáticamente la OC de inventario seller "
            f"<b>{po.name}</b> sin generar una recepción adicional."
        )
        return po

    def _mkp_confirm_settlement_po(self, po):
        self.ensure_one()
        try:
            if po.state in ("draft", "sent"):
                po.button_confirm()
            if po.state == "to approve":
                po.sudo().button_approve()
        except Exception as error:
            raise ValidationError(
                f"No fue posible confirmar la orden de compra {po.display_name}. "
                f"Detalle: {error}"
            )
        if po.state not in ("purchase", "done"):
            raise ValidationError(
                f"La orden de compra {po.display_name} quedó en estado "
                f"'{po.state}' y no pudo ejecutarse automáticamente."
            )

    def _mkp_cancel_related_pos(self):
        self.ensure_one()
        pos = self.env["purchase.order"].search(
            [
                ("mkp_sale_order_id", "=", self.id),
                ("mkp_seller_settlement", "=", True),
                ("company_id", "=", self.company_id.id),
                ("state", "in", ["draft", "sent", "to approve", "purchase"]),
            ]
        )
        for po in pos:
            try:
                po.button_cancel()
            except Exception as e:
                self.message_post(body=f"No se pudo cancelar la PO {po.name}, error: {str(e)}")
