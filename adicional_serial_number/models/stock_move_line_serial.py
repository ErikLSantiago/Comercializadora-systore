
from odoo import api, fields, models


class StockMoveLineSerial(models.Model):
    _name = "stock.move.line.serial"
    _description = "Seriales capturados adicionales"
    _order = "id desc"

    name = fields.Char("Número de serie", required=True, index=True)
    product_id = fields.Many2one("product.product", string="Producto", required=True, index=True)
    picking_id = fields.Many2one("stock.picking", string="Operación", required=True, index=True)
    move_line_id = fields.Many2one("stock.move.line", string="Línea de operación", index=True)
    lot_id = fields.Many2one("stock.lot", string="Lote")
    date = fields.Datetime("Fecha", default=fields.Datetime.now, readonly=True)
    company_id = fields.Many2one("res.company", string="Compañía", default=lambda self: self.env.company.id, readonly=True)

    # Campos de contexto para reporteo
    partner_id = fields.Many2one(related="picking_id.partner_id", string="Contacto", store=False, readonly=True)
    origin = fields.Char(related="picking_id.origin", string="Origen", store=False, readonly=True)
    carrier_tracking_ref = fields.Char(related="picking_id.carrier_tracking_ref", string="Guía", store=False, readonly=True)
    lot_name = fields.Char(related="lot_id.name", string="Nombre de lote", store=False, readonly=True)

    _sql_constraints = [
        ("serial_unique_per_picking", "unique(name,picking_id)",
         "El número de serie ya fue capturado en esta operación."),
    ]
