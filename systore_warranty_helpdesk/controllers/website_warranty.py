import base64
import json

from odoo import http
from odoo.http import request


class WarrantyWebsiteController(http.Controller):

    @http.route(
        ["/garantias/solicitud"],
        type="http",
        auth="public",
        website=True,
        methods=["GET", "POST"],
    )
    def warranty_request(self, **post):
        """Formulario para solicitud de garantías -> crea helpdesk.ticket."""

        user = request.env.user
        is_logged_in = not user._is_public()

        if not is_logged_in:
            # Redirigir a login si el usuario no ha iniciado sesión
            return request.redirect('/web/login?redirect=/garantias/solicitud')

        if request.httprequest.method == "POST":
            # Validar check de términos
            if not post.get("terms_accepted"):
                return request.render(
                    "systore_warranty_helpdesk.warranty_request_template",
                    {
                        "post": post,
                        "is_logged_in": is_logged_in,
                        "error_terms": True,
                        "success": False,
                    },
                )

            HelpdeskTicket = request.env["helpdesk.ticket"].sudo()
            SaleOrder = request.env["sale.order"].sudo()
            Product = request.env["product.product"].sudo()

            no_order_found = bool(post.get("no_order_found"))

            sale_order = False
            product = False

            # Intentar resolver la orden por ID oculto (seleccionada desde el autocompletado)
            sale_order_id_str = post.get("sale_order_id")
            sale_order_name = post.get("sale_order_name") or False

            if not no_order_found:
                if sale_order_id_str and sale_order_id_str.isdigit():
                    sale_order = SaleOrder.browse(int(sale_order_id_str))
                    if not sale_order.exists():
                        sale_order = False

                # Si no se pudo por ID, buscar por nombre / referencia
                if not sale_order and sale_order_name:
                    term = sale_order_name.strip()
                    domain = [
                        "|",
                        ("name", "=", term),
                        ("client_order_ref", "=", term),
                    ]

                    sale_order = SaleOrder.search(domain, limit=1)

                    # Búsqueda parcial si no se encontró exacto
                    if not sale_order:
                        domain[-3:] = [("name", "ilike", term)]
                        sale_order = SaleOrder.search(domain, limit=1)

            # Si hay orden y producto elegido
            product_id = post.get("product_id")
            if sale_order and product_id and not no_order_found:
                try:
                    product = Product.browse(int(product_id))
                except Exception:
                    product = Product.browse(False)

            # Datos de contacto y falla
            phone = post.get("warranty_phone")
            imei = post.get("warranty_imei")
            failure_type = post.get("failure_type")
            failure_type_other = post.get("failure_type_other")
            failure_description = post.get("failure_description")

            # Datos cuando no encontró la orden
            manual_order_number = post.get("manual_order_number")
            manual_product_description = post.get("manual_product_description")

            # Descripción del ticket
            description_lines = []

            if no_order_found:
                description_lines.append("El cliente NO encontró su número de orden.")
                if manual_order_number:
                    description_lines.append(
                        f"Número de orden proporcionado: {manual_order_number}"
                    )
                if manual_product_description:
                    description_lines.append(
                        f"Descripción de producto proporcionada: {manual_product_description}"
                    )
            else:
                if sale_order:
                    description_lines.append(f"Orden de venta: {sale_order.name}")
                if product:
                    description_lines.append(
                        f"Producto: {product.display_name} (SKU: {product.default_code or 'N/A'})"
                    )

            if phone:
                description_lines.append(f"Teléfono de contacto: {phone}")
            if imei:
                description_lines.append(f"Número de serie / IMEI: {imei}")
            if failure_type:
                failure_selection = dict(
                    request.env["helpdesk.ticket"].fields_get(
                        ["failure_type"]
                    )["failure_type"]["selection"]
                )
                txt = failure_selection.get(failure_type, failure_type)
                description_lines.append(f"Tipo de falla: {txt}")
            if failure_type == "otro" and failure_type_other:
                description_lines.append(
                    f"Tipo de falla (otro): {failure_type_other}"
                )
            if failure_description:
                description_lines.append(
                    "Descripción de la falla:\n" + failure_description
                )

            description_full = "\n".join(description_lines)

            vals = {
            "name": "Ticket-",
                
                "is_warranty": True,
                "warranty_phone": phone,
                "warranty_imei": imei,
                "failure_type": failure_type,
                "failure_type_other": failure_type_other
                if failure_type == "otro"
                else False,
                "failure_description": failure_description,
                "description": description_full,
                "no_order_found": no_order_found,
                "manual_order_number": manual_order_number if no_order_found else False,
                "manual_product_description": manual_product_description
                if no_order_found
                else False,
            }

            # Asociar el partner del usuario logueado para permitir notificaciones nativas
            partner = user.partner_id
            if partner:
                vals["partner_id"] = partner.id

            # Forzar compañía coherente para evitar errores de empresa/cliente
            if sale_order and sale_order.company_id:
                vals["company_id"] = sale_order.company_id.id
            elif user.company_id:
                vals["company_id"] = user.company_id.id

            # Asociar orden/producto SOLO si sí se encontró la orden
            if sale_order and not no_order_found:
                vals["sale_order_id"] = sale_order.id
                if product:
                    vals["product_id"] = product.id

            # Asignar equipo de Helpdesk 'Garantías'
            team = None
            # 1) Intentar localizar por external ID del módulo
            try:
                team = request.env.ref("systore_warranty_helpdesk.helpdesk_team_warranty")
            except Exception:
                team = None
            # 2) Si no existe ese external ID, buscar por nombre
            if not team:
                team = request.env["helpdesk.team"].sudo().search([("name", "=", "Garantías")], limit=1)
            if team:
                vals["team_id"] = team.id

            # Crear el ticket
            ticket = HelpdeskTicket.create(vals)
            # Construir nombre del ticket: número de ticket, número de orden y SKU
            # Usamos el ID interno como número de ticket legible
            ticket_number = f"Ticket-{ticket.id}"

            order_part = sale_order.name if sale_order and not no_order_found else False
            sku_part = (
                (product.default_code or product.name)
                if (product and not no_order_found)
                else False
            )

            parts = [ticket_number]
            if order_part:
                parts.append(order_part)
            if sku_part:
                parts.append(sku_part)

            ticket.name = " - ".join(parts) if parts else ticket_number


            # Enviar correo usando la plantilla configurada en la etapa (si aplica)
            try:
                stage = ticket.stage_id
                template = getattr(stage, "mail_template_id", False) or getattr(stage, "template_id", False)
                if template and ticket.partner_id:
                    template.sudo().send_mail(ticket.id, force_send=True)
            except Exception:
                # En caso de fallo en el envío, no bloquear el flujo del portal
                pass

            # Procesar evidencias (archivos adjuntos)
            file_fields = {
                "evidence_failure": "Identificación de la falla",
                "evidence_left": "Lado lateral izquierda",
                "evidence_right": "Lado lateral derecha",
                "evidence_top": "Lado superior",
                "evidence_bottom": "Lado inferior",
                "evidence_front": "Frente pantalla",
                "evidence_back": "Tapa trasera o parte posterior",
            }

            # Adjuntar evidencias directamente al chatter del ticket mediante ir.attachment
            # Solo se permiten archivos de imagen: .jpg, .jpeg, .png, .gif
            allowed_ext = {".jpg", ".jpeg", ".png", ".gif"}
            Attachment = request.env["ir.attachment"].sudo()
            attachment_ids = []
            attached_labels = []

            for field_name, desc in file_fields.items():
                uploaded_file = request.httprequest.files.get(field_name)
                if uploaded_file and uploaded_file.filename:
                    filename = uploaded_file.filename
                    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
                    if ext not in allowed_ext:
                        continue

                    data = uploaded_file.read()
                    attachment = Attachment.create(
                        {
                            "name": filename,
                            "datas": base64.b64encode(data),
                            "mimetype": uploaded_file.mimetype or "application/octet-stream",
                            "res_model": "helpdesk.ticket",
                            "res_id": ticket.id,
                            "description": desc,
                        }
                    )
                    attachment_ids.append(attachment.id)
                    attached_labels.append(desc)

            if attachment_ids:
                body = "Evidencias de garantía adjuntas."
                if attached_labels:
                    body += "<br/>Archivos cargados:<ul>"
                    for lbl in attached_labels:
                        body += "<li>%s</li>" % lbl
                    body += "</ul>"

                ticket.message_post(
                    body=body,
                    attachment_ids=attachment_ids,
                )

            return request.render(
                "systore_warranty_helpdesk.warranty_request_template",
                {
                    "is_logged_in": is_logged_in,
                    "success": True,
                    "ticket": ticket,
                    "post": {},
                },
            )

        # GET: mostrar formulario vacío
        return request.render(
            "systore_warranty_helpdesk.warranty_request_template",
            {
                "is_logged_in": is_logged_in,
                "success": False,
                "post": {},
            },
        )


    @http.route(
        ["/garantias/order_search"],
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def warranty_order_search(self, **kwargs):
        """Devuelve sugerencias de órdenes de venta (sin restricción por usuario)."""
        user = request.env.user
        data = []

        term = (kwargs.get("term") or "").strip()
        if len(term) >= 4:
            SaleOrder = request.env["sale.order"].sudo()

            # Dominio base (sin restricción de partner)
            domain = [
                "|",
                ("name", "ilike", term),
                ("client_order_ref", "ilike", term),
            ]

            # Sin restricción por cliente: se permite buscar cualquier orden
            orders = SaleOrder.search(domain, limit=10)
            for o in orders:
                label = o.name
                if o.client_order_ref:
                    label = f"{o.name} ({o.client_order_ref})"
                data.append(
                    {
                        "id": o.id,
                        "name": o.name,
                        "label": label,
                    }
                )

        body = json.dumps(data)
        return request.make_response(
            body, headers=[("Content-Type", "application/json")]
        )


    @http.route(
        ["/garantias/order_products"],
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def warranty_order_products(self, **kwargs):
        """Devuelve los productos de la orden seleccionada para poblar el combo (sin restricción por usuario)."""
        user = request.env.user
        data = []

        order_id = kwargs.get("order_id")
        if order_id and str(order_id).isdigit():
            SaleOrder = request.env["sale.order"].sudo()
            order = SaleOrder.browse(int(order_id))
            if order.exists():
                # Sin restricción por cliente: usar siempre la orden encontrada
                for line in order.order_line:
                    if line.product_id:
                        label = line.product_id.display_name
                        if line.product_id.default_code:
                            label = f"[{line.product_id.default_code}] {label}"
                        data.append(
                            {
                                "id": line.product_id.id,
                                "name": line.product_id.display_name,
                                "code": line.product_id.default_code or "",
                                "label": label,
                            }
                        )

        body = json.dumps(data)
        return request.make_response(
            body, headers=[("Content-Type", "application/json")]
        )
