from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero


class MeatCuttingOrder(models.Model):
    _name = "meat.cutting.order"
    _description = "Orden de Despiece"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(default="New", copy=False, readonly=True, tracking=True)
    state = fields.Selection([
        ("draft", "Borrador"),
        ("calculated", "Calculado"),
        ("confirmed", "Confirmado"),
        ("done", "Hecho"),
        ("cancel", "Cancelado"),
    ], default="draft", tracking=True)

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)

    product_src_id = fields.Many2one("product.product", required=True, string="Producto Origen")
    lot_src_id = fields.Many2one(
        "stock.lot",
        required=True,
        string="Lote Origen",
        domain="[('product_id','=',product_src_id)]",
    )
    location_src_id = fields.Many2one(
        "stock.location",
        required=True,
        string="Ubicación Origen",
        domain="[('usage','=','internal')]",
    )

    # Opcional: si viene vacío, se usa un default (picking type / compañía)
    location_dest_id = fields.Many2one(
        "stock.location",
        string="Ubicación Destino",
        required=False,
        domain="[('usage','=','internal')]",
    )

    weight_consume_kg = fields.Float(string="Peso a Consumir (kg)", required=True, digits="Product Unit of Measure")
    tolerance_kg = fields.Float(string="Tolerancia (kg)", default=0.01, digits="Product Unit of Measure")

    line_ids = fields.One2many("meat.cutting.order.line", "order_id", string="Resultados")

    weight_total_produced_kg = fields.Float(string="Peso Total Producido (kg)", compute="_compute_weights", store=True)
    picking_id = fields.Many2one("stock.picking", copy=False, readonly=True)
    picking_type_id = fields.Many2one("stock.picking.type", readonly=True, copy=False)

    production_location_id = fields.Many2one(
        "stock.location",
        string="Ubicación Técnica (Despiece)",
        required=True,
        default=lambda self: self.env.ref("meat_cutting.stock_location_meat_cutting_production"),
        domain="[('usage','in',('production','inventory'))]",
    )

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = seq.next_by_code("meat.cutting.order") or "New"
        return super().create(vals_list)

    @api.depends("line_ids.weight_total_kg")
    def _compute_weights(self):
        for o in self:
            o.weight_total_produced_kg = sum(o.line_ids.mapped("weight_total_kg"))

    def action_calculate(self):
        for o in self:
            o._check_weights()
            o.state = "calculated"

    def _check_weights(self):
        self.ensure_one()
        if self.weight_consume_kg <= 0:
            raise UserError(_("El peso a consumir debe ser > 0."))

        if not self.line_ids:
            raise UserError(_("Agrega al menos una línea de producto resultante."))

        for l in self.line_ids:
            if l.qty_done <= 0 or l.weight_unit_kg <= 0:
                raise UserError(_("Cantidad y peso por unidad deben ser > 0 en todas las líneas."))

            # Lote obligatorio solo si el producto es tracking por LOTE (no serial)
            if l.product_id.tracking == "lot" and not l.lot_id:
                raise UserError(_("El lote es obligatorio para productos con seguimiento por Lote: %s") % l.product_id.display_name)

            # Serial requiere cantidad entera
            if l.product_id.tracking == "serial":
                qty_int = int(l.qty_done)
                if float(qty_int) != float(l.qty_done):
                    raise UserError(_("Para productos con seguimiento por Número de serie, la cantidad debe ser un entero. Producto: %s") % l.product_id.display_name)

        diff = self.weight_total_produced_kg - self.weight_consume_kg
        if abs(diff) > self.tolerance_kg:
            raise UserError(_(
                "La suma de pesos producidos (%s kg) no cuadra con el peso consumido (%s kg). "
                "Diferencia: %s kg (tolerancia %s kg)."
            ) % (self.weight_total_produced_kg, self.weight_consume_kg, diff, self.tolerance_kg))

    def _next_serial_name(self):
        self.ensure_one()
        return self.env["ir.sequence"].next_by_code("meat_cutting.serial") or _("C-0000")

    def _get_default_dest_location(self, picking_type):
        if self.location_dest_id:
            return self.location_dest_id
        if picking_type.default_location_dest_id:
            return picking_type.default_location_dest_id
        company_stock_loc = getattr(self.company_id, "stock_location_id", False)
        if company_stock_loc:
            return company_stock_loc
        raise UserError(_("No hay una ubicación destino por defecto configurada."))

    def action_confirm(self):
        for o in self:
            o._check_weights()
            if o.picking_id:
                raise UserError(_("Esta orden ya tiene un picking asociado."))

            picking_type = o.env.ref("meat_cutting.picking_type_meat_cutting")
            o.picking_type_id = picking_type.id
            dest = o._get_default_dest_location(picking_type)

            picking = o.env["stock.picking"].create({
                "picking_type_id": picking_type.id,
                "location_id": o.location_src_id.id,
                "location_dest_id": dest.id,
                "origin": o.name,
                "company_id": o.company_id.id,
            })
            o.picking_id = picking.id

            # Consumo (kg) Existencias -> Ubicación Técnica (Producción/Despiece)
            move_out = o.env["stock.move"].create({
                "name": _("Consumo %s") % o.product_src_id.display_name,
                "product_id": o.product_src_id.id,
                "product_uom": o.product_src_id.uom_id.id,
                "product_uom_qty": o.weight_consume_kg,
                "location_id": o.location_src_id.id,
                "location_dest_id": o.production_location_id.id,
                "picking_id": picking.id,
                "company_id": o.company_id.id,
                "x_cutting_order_id": o.id,
                "x_weight_total_kg": o.weight_consume_kg,
            })
            o.env["stock.move.line"].create({
                "move_id": move_out.id,
                "picking_id": picking.id,
                "product_id": o.product_src_id.id,
                "product_uom_id": o.product_src_id.uom_id.id,
                "qty_done": o.weight_consume_kg,
                "location_id": o.location_src_id.id,
                "location_dest_id": o.production_location_id.id,
                "lot_id": o.lot_src_id.id,
                "company_id": o.company_id.id,
            })

            # Entradas (pzas) Ubicación Técnica -> Destino final
            for l in o.line_ids:
                move_in = o.env["stock.move"].create({
                    "name": _("Resultado %s") % l.product_id.display_name,
                    "product_id": l.product_id.id,
                    "product_uom": l.product_id.uom_id.id,
                    "product_uom_qty": l.qty_done,
                    "location_id": o.production_location_id.id,
                    "location_dest_id": dest.id,
                    "picking_id": picking.id,
                    "company_id": o.company_id.id,
                    "x_cutting_order_id": o.id,
                    "x_weight_total_kg": l.weight_total_kg,
                })

                if l.product_id.tracking == "serial":
                    qty_int = int(l.qty_done)
                    for _i in range(qty_int):
                        serial_name = o._next_serial_name()
                        lot = o.env["stock.lot"].create({
                            "name": serial_name,
                            "product_id": l.product_id.id,
                            "company_id": o.company_id.id,
                            "x_weight_kg": l.weight_unit_kg,
                        })
                        o.env["stock.move.line"].create({
                            "move_id": move_in.id,
                            "picking_id": picking.id,
                            "product_id": l.product_id.id,
                            "product_uom_id": l.product_id.uom_id.id,
                            "qty_done": 1.0,
                            "location_id": o.production_location_id.id,
                            "location_dest_id": dest.id,
                            "lot_id": lot.id,
                            "x_weight_kg": l.weight_unit_kg,
                            "company_id": o.company_id.id,
                        })
                else:
                    o.env["stock.move.line"].create({
                        "move_id": move_in.id,
                        "picking_id": picking.id,
                        "product_id": l.product_id.id,
                        "product_uom_id": l.product_id.uom_id.id,
                        "qty_done": l.qty_done,
                        "location_id": o.production_location_id.id,
                        "location_dest_id": dest.id,
                        "lot_id": l.lot_id.id if l.lot_id else False,
                        "x_weight_kg": l.weight_unit_kg,
                        "company_id": o.company_id.id,
                    })

            o.state = "confirmed"

    def action_done(self):
        for o in self:
            if o.state != "confirmed":
                raise UserError(_("La orden debe estar en estado Confirmado."))
            o._check_weights()
            if not o.picking_id:
                raise UserError(_("No hay picking asociado."))

            o.picking_id.button_validate()

            # Distribución contable (SVL) - si tu build tiene firma distinta, ajustamos con el traceback.
            o._apply_weight_cost_distribution()

            o.state = "done"

def _apply_weight_cost_distribution(self):
    """Distribuye el valor consumido del origen hacia los movimientos de entrada (resultantes),
    actualizando SVL existentes (creados por la validación del picking) y ajustando el valor de quants
    para que el reporte de existencias muestre el valor por número de serie/lote.
    """
    self.ensure_one()
    picking = self.picking_id
    moves = picking.move_ids_without_package

    move_out = moves.filtered(lambda m: m.product_id.id == self.product_src_id.id and m.location_id.id == self.location_src_id.id)
    move_ins = (moves - move_out)

    if not move_out:
        raise UserError(_("No se encontró el movimiento de consumo."))

    # Valor consumido (FIFO por lote)
    svls_out = self.env["stock.valuation.layer"].search([("stock_move_id", "in", move_out.ids)])
    value_consumed = -sum(svls_out.mapped("value"))  # salida es negativa

    if float_is_zero(value_consumed, precision_rounding=0.00001):
        raise UserError(_("No se detectó valor consumido en SVL. Revisa FIFO/valuación automatizada en el producto origen."))

    total_weight = sum(move_ins.mapped("x_weight_total_kg"))
    if float_is_zero(total_weight, precision_rounding=0.00001):
        raise UserError(_("Peso total de entradas es 0."))

    remaining = value_consumed
    move_ins_sorted = move_ins.sorted(key=lambda m: m.id)

    for idx, m in enumerate(move_ins_sorted, start=1):
        w = m.x_weight_total_kg or 0.0
        if idx < len(move_ins_sorted):
            value_line = value_consumed * (w / total_weight)
            remaining -= value_line
        else:
            value_line = remaining

        qty = sum(m.move_line_ids.mapped("qty_done")) or 0.0
        if qty <= 0:
            continue

        unit_cost = value_line / qty

        # 1) Actualizar SVL(s) existentes del move
        svls_in = self.env["stock.valuation.layer"].search([("stock_move_id", "=", m.id)])
        old_value = sum(svls_in.mapped("value")) if svls_in else 0.0
        diff_value = value_line - old_value

        if svls_in:
            first = svls_in[0]
            first.write({
                "unit_cost": unit_cost,
                "value": value_line,
                "remaining_value": value_line,
                "remaining_qty": qty,
                "quantity": qty,
                "description": _("Despiece %s") % self.name,
            })
            if len(svls_in) > 1:
                for extra in svls_in[1:]:
                    extra.write({"unit_cost": 0.0, "value": 0.0, "remaining_value": 0.0, "remaining_qty": 0.0})
        else:
            self.env["stock.valuation.layer"].create({
                "stock_move_id": m.id,
                "company_id": self.company_id.id,
                "product_id": m.product_id.id,
                "quantity": qty,
                "unit_cost": unit_cost,
                "value": value_line,
                "remaining_value": value_line,
                "remaining_qty": qty,
                "description": _("Despiece %s") % self.name,
            })
            diff_value = value_line

        # 2) Ajuste contable: registrar SOLO la diferencia
        if not float_is_zero(diff_value, precision_rounding=0.00001) and hasattr(m, "_account_entry_move"):
            svl_for_call = self.env["stock.valuation.layer"].search([("stock_move_id","=",m.id)], limit=1)
            try:
                m._account_entry_move(qty, _("Despiece %s") % self.name, svl_for_call.id if svl_for_call else False, diff_value)
            except TypeError:
                m._account_entry_move(qty, _("Despiece %s") % self.name, svl_for_call, diff_value)

        # 3) Forzar valor en quants (para que el listado de existencias muestre valor por serial/lote)
        Quant = self.env["stock.quant"]
        for ml in m.move_line_ids:
            quant_domain = [
                ("product_id", "=", m.product_id.id),
                ("location_id", "=", m.location_dest_id.id),
            ]
            if ml.lot_id:
                quant_domain.append(("lot_id", "=", ml.lot_id.id))
            q = Quant.search(quant_domain, limit=1)
            if not q:
                continue
            ml_qty = ml.qty_done or 0.0
            q_value = unit_cost * ml_qty
            vals = {}
            if "value" in q._fields:
                vals["value"] = q_value
            if "inventory_value" in q._fields:
                vals["inventory_value"] = q_value
            if vals:
                q.write(vals)


class MeatCuttingOrderLine(models.Model):
    _name = "meat.cutting.order.line"
    _description = "Líneas de Despiece"

    order_id = fields.Many2one("meat.cutting.order", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", required=True, string="Producto Resultante")
    qty_done = fields.Float(string="Cantidad Hecha (pzas)", required=True, digits="Product Unit of Measure")
    weight_unit_kg = fields.Float(string="Peso por Unidad (kg)", required=True, digits="Product Unit of Measure")
    weight_total_kg = fields.Float(string="Peso Total (kg)", compute="_compute_weight_total", store=True)

    # Opcional para serial (se auto-genera). Obligatorio si tracking=lot (validación en _check_weights)
    lot_id = fields.Many2one("stock.lot", required=False, string="Lote Resultante",
                             domain="[('product_id','=',product_id)]")

    @api.depends("qty_done", "weight_unit_kg")
    def _compute_weight_total(self):
        for l in self:
            l.weight_total_kg = (l.qty_done or 0.0) * (l.weight_unit_kg or 0.0)
