# -*- coding: utf-8 -*-
from odoo import api, fields, models
from psycopg2 import errors
from collections import defaultdict


class ProductWarehouseCost(models.Model):
    _name = "product.warehouse.cost"
    _description = "Costo promedio por almacén para producto"
    _order = "warehouse_id"

    company_id = fields.Many2one(
        "res.company", required=True, index=True, default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True, readonly=True
    )

    product_id = fields.Many2one("product.product", required=True, ondelete="cascade", index=True)
    warehouse_id = fields.Many2one("stock.warehouse", required=True, index=True)

    product_tmpl_id = fields.Many2one(
        "product.template", related="product_id.product_tmpl_id", store=True, index=True, readonly=True
    )

    qty_on_hand = fields.Float("Cantidad", digits="Product Unit of Measure", readonly=True)
    reserved_qty = fields.Float("Reservadas", digits="Product Unit of Measure", readonly=True)
    available_qty = fields.Float("Disponibles", digits="Product Unit of Measure", readonly=True)

    total_value = fields.Monetary(
        "VT",
        currency_field="currency_id",
        readonly=True,
        help="Suma de inventory_value (o value) de los quants del producto dentro del almacén.",
    )
    unit_value = fields.Monetary(
        "CPT",
        currency_field="currency_id",
        readonly=True,
        help="Costo Promedio de Piezas Totales en almacén: VT ÷ Cantidad."
    )
    available_value = fields.Monetary(
        "VD",
        currency_field="currency_id",
        readonly=True,
        help="Valor de Piezas Disponibles en almacén: CPT × Disponibles."
    )
    proposed_avg_cost = fields.Monetary(
        "CPD",
        currency_field="currency_id",
        readonly=True,
        help="Costo Promedio Disponible en almacén: VD ÷ Disponibles (si Disponibles > 0)."
    )

    _sql_constraints = [
        ("uniq_product_warehouse", "unique(product_id, warehouse_id)", "Ya existe un registro para este producto y almacén."),
    ]


class ProductProduct(models.Model):
    _inherit = "product.product"

    proposed_avg_cost_global = fields.Monetary(
        string="Costo Promedio Disponible General",
        currency_field="currency_id",
        compute="_compute_proposed_avg_cost_global",
        help="Promedio ponderado usando SOLO piezas DISPONIBLES bajo los almacenes visibles: "
             "Σ(CPT_almacén × Disponibles_almacén) ÷ Σ(Disponibles_almacén).",
    )
    total_avg_cost_global = fields.Monetary(
        string="Costo Promedio Total General",
        currency_field="currency_id",
        compute="_compute_total_avg_cost_global",
        help="Promedio ponderado usando TODAS las piezas (incluye reservadas): "
             "Σ(Valor_total_almacén) ÷ Σ(Cantidad_almacén).",
    )

    warehouse_cost_line_ids = fields.One2many(
        "product.warehouse.cost",
        "product_id",
        string="Costos por almacén",
        compute="_compute_warehouse_cost_lines",
        readonly=True,
        compute_sudo=True,
    )

    def _rebuild_warehouse_cost_lines(self):
        Quant = self.env["stock.quant"].sudo()
        Warehouse = self.env["stock.warehouse"].sudo()
        warehouses = Warehouse.search([("company_id", "in", self.env.companies.ids)])

        for product in self:
            new_lines = []
            # Lock NOWAIT para evitar conflictos durante exportaciones/otras lecturas
            try:
                self.env.cr.execute(
                    "SELECT id FROM product_warehouse_cost WHERE product_id=%s FOR UPDATE NOWAIT",
                    (product.id,),
                )
            except Exception:
                # Si no se puede bloquear, omitir este producto en este ciclo
                continue

            for wh in warehouses:
                quants = Quant.search([
                    ("product_id", "=", product.id),
                    ("company_id", "=", wh.company_id.id),
                    ("location_id", "child_of", wh.view_location_id.id),
                    ("location_id.usage", "=", "internal"),
                    ("quantity", ">", 0.0),
                ])
                if not quants:
                    continue

                qty = sum(q.quantity for q in quants)
                reserved = sum(q.reserved_quantity for q in quants)
                if qty <= 0.0:
                    continue

                total_val = 0.0
                for q in quants:
                    inv_val = getattr(q, "inventory_value", None)
                    if inv_val is None:
                        inv_val = getattr(q, "value", 0.0)
                    total_val += inv_val or 0.0

                available = max(qty - reserved, 0.0)
                unit_value = (total_val / qty) if qty else 0.0
                available_value = unit_value * available
                proposed = (available_value / available) if available else 0.0

                new_lines.append({
                    "product_id": product.id,
                    "warehouse_id": wh.id,
                    "qty_on_hand": qty,
                    "reserved_qty": reserved,
                    "available_qty": available,
                    "total_value": total_val,
                    "unit_value": unit_value,
                    "available_value": available_value,
                    "proposed_avg_cost": proposed,
                    "company_id": wh.company_id.id,
                })

            if new_lines:
                try:
                    with self.env.cr.savepoint():
                        self.env["product.warehouse.cost"].sudo().search([("product_id", "=", product.id)]).unlink()
                        self.env["product.warehouse.cost"].sudo().create(new_lines)
                except (errors.SerializationFailure, Exception):
                    # En conflicto de concurrencia, omitir sin romper la llamada
                    continue

    def _compute_warehouse_cost_lines(self):
        Cost = self.env["product.warehouse.cost"].sudo()
        for rec in self:
            try:
                rec._rebuild_warehouse_cost_lines()
            except Exception:
                # Si falla el rebuild, devolvemos las líneas existentes
                pass
            ids = Cost.search([("product_id", "=", rec.id)]).ids
            rec.warehouse_cost_line_ids = [(6, 0, ids)]

    def _compute_proposed_avg_cost_global(self):
        Quant = self.env["stock.quant"].sudo()
        Warehouse = self.env["stock.warehouse"].sudo()
        warehouses = Warehouse.search([("company_id", "in", self.env.companies.ids)])
        roots = [wh.view_location_id.id for wh in warehouses]

        for product in self:
            if not roots:
                product.proposed_avg_cost_global = 0.0
                continue
            quants = Quant.search([
                ("product_id", "=", product.id),
                ("location_id.usage", "=", "internal"),
                ("quantity", ">", 0.0),
                ("location_id", "child_of", roots),
            ])
            total_available_qty = 0.0
            total_available_value = 0.0
            for q in quants:
                qty = q.quantity or 0.0
                reserved = q.reserved_quantity or 0.0
                available = max(qty - reserved, 0.0)
                if available <= 0.0:
                    continue
                inv_val = getattr(q, "inventory_value", None)
                if inv_val is None:
                    inv_val = getattr(q, "value", 0.0)
                total_value = inv_val or 0.0
                unit_value = (total_value / qty) if qty else 0.0
                total_available_qty += available
                total_available_value += unit_value * available
            product.proposed_avg_cost_global = (total_available_value / total_available_qty) if total_available_qty else 0.0

    def _compute_total_avg_cost_global(self):
        Quant = self.env["stock.quant"].sudo()
        Warehouse = self.env["stock.warehouse"].sudo()
        warehouses = Warehouse.search([("company_id", "in", self.env.companies.ids)])
        roots = [wh.view_location_id.id for wh in warehouses]

        for product in self:
            if not roots:
                product.total_avg_cost_global = 0.0
                continue
            quants = Quant.search([
                ("product_id", "=", product.id),
                ("location_id.usage", "=", "internal"),
                ("quantity", ">", 0.0),
                ("location_id", "child_of", roots),
            ])
            total_qty = 0.0
            total_value = 0.0
            for q in quants:
                qty = q.quantity or 0.0
                if qty <= 0.0:
                    continue
                inv_val = getattr(q, "inventory_value", None)
                if inv_val is None:
                    inv_val = getattr(q, "value", 0.0)
                total_qty += qty
                total_value += inv_val or 0.0
            product.total_avg_cost_global = (total_value / total_qty) if total_qty else 0.0


class ProductTemplate(models.Model):
    _inherit = "product.template"

    proposed_avg_cost_global_tpl = fields.Monetary(
        string="Costo Promedio Disponible General",
        currency_field="currency_id",
        compute="_compute_tpl_avg_cost",
        help="Promedio ponderado con SOLO piezas DISPONIBLES de todas las variantes bajo los almacenes visibles.",
    )
    total_avg_cost_global_tpl = fields.Monetary(
        string="Costo Promedio Total General",
        currency_field="currency_id",
        compute="_compute_tpl_total_avg_cost",
        help="Promedio ponderado con TODAS las piezas de todas las variantes bajo los almacenes visibles.",
    )

    warehouse_cost_line_ids_tmpl = fields.One2many(
        "product.warehouse.cost",
        "product_tmpl_id",
        string="Costos por almacén",
        compute="_compute_warehouse_cost_lines_tmpl",
        readonly=True,
        compute_sudo=True,
    )

    def _compute_warehouse_cost_lines_tmpl(self):
        Cost = self.env["product.warehouse.cost"].sudo()
        # No rebuild aquí para exportaciones masivas (solo lectura)
        costs = Cost.search([("product_tmpl_id", "in", self.ids)])
        by_tmpl = defaultdict(list)
        for c in costs:
            if c.product_tmpl_id:
                by_tmpl[c.product_tmpl_id.id].append(c.id)
        for rec in self:
            rec.warehouse_cost_line_ids_tmpl = [(6, 0, by_tmpl.get(rec.id, []))]

    def _compute_tpl_avg_cost(self):
        Quant = self.env["stock.quant"].sudo()
        Warehouse = self.env["stock.warehouse"].sudo()
        warehouses = Warehouse.search([("company_id", "in", self.env.companies.ids)])
        roots = [wh.view_location_id.id for wh in warehouses]

        for template in self:
            products = template.product_variant_ids
            if not products or not roots:
                template.proposed_avg_cost_global_tpl = 0.0
                continue
            quants = Quant.search([
                ("product_id", "in", products.ids),
                ("location_id.usage", "=", "internal"),
                ("quantity", ">", 0.0),
                ("location_id", "child_of", roots),
            ])
            total_available_qty = 0.0
            total_available_value = 0.0
            for q in quants:
                qty = q.quantity or 0.0
                reserved = q.reserved_quantity or 0.0
                available = max(qty - reserved, 0.0)
                if available <= 0.0:
                    continue
                inv_val = getattr(q, "inventory_value", None)
                if inv_val is None:
                    inv_val = getattr(q, "value", 0.0)
                total_value = inv_val or 0.0
                unit_value = (total_value / qty) if qty else 0.0
                total_available_qty += available
                total_available_value += unit_value * available
            template.proposed_avg_cost_global_tpl = (total_available_value / total_available_qty) if total_available_qty else 0.0

    def _compute_tpl_total_avg_cost(self):
        Quant = self.env["stock.quant"].sudo()
        Warehouse = self.env["stock.warehouse"].sudo()
        warehouses = Warehouse.search([("company_id", "in", self.env.companies.ids)])
        roots = [wh.view_location_id.id for wh in warehouses]

        for template in self:
            products = template.product_variant_ids
            if not products or not roots:
                template.total_avg_cost_global_tpl = 0.0
                continue
            quants = Quant.search([
                ("product_id", "in", products.ids),
                ("location_id.usage", "=", "internal"),
                ("quantity", ">", 0.0),
                ("location_id", "child_of", roots),
            ])
            total_qty = 0.0
            total_value = 0.0
            for q in quants:
                qty = q.quantity or 0.0
                if qty <= 0.0:
                    continue
                inv_val = getattr(q, "inventory_value", None)
                if inv_val is None:
                    inv_val = getattr(q, "value", 0.0)
                total_qty += qty
                total_value += inv_val or 0.0
            template.total_avg_cost_global_tpl = (total_value / total_qty) if total_qty else 0.0
