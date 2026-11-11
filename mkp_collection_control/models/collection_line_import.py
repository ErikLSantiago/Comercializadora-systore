from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .collection_line_history import MONETARY_REVISION_FIELDS


class MkpCollectionLineImport(models.Model):
    _name = 'mkp.collection.line.import'
    _description = 'Importación de comisiones por línea'
    _order = 'id desc'
    _rec_name = 'sale_order_id'

    sale_order_id = fields.Many2one(
        'sale.order', string='Orden de venta', required=True, index=True,
        ondelete='restrict'
    )
    sku = fields.Char('SKU', required=True, index=True)
    line_sequence = fields.Integer('Secuencia de línea')
    coupon_amount = fields.Monetary('Cupón', currency_field='currency_id')
    killer_amount = fields.Monetary('Killer', currency_field='currency_id')
    killer_commission = fields.Monetary('Comisión killer', currency_field='currency_id')
    commission = fields.Monetary('Comisiones', currency_field='currency_id')
    taxes = fields.Monetary('Impuestos', currency_field='currency_id')
    shipping = fields.Monetary('Envío', currency_field='currency_id')
    other_commission = fields.Monetary('Otras comisiones', currency_field='currency_id')
    calculation_type = fields.Selection([
        ('precalculation', 'Precalculo'),
        ('marketplace', 'Marketplace'),
    ], string='Tipo de cálculo')
    payment_status = fields.Selection([
        ('held', 'Retenido'),
        ('pending', 'Pendiente'),
        ('paid', 'Pagado'),
        ('cancelled', 'Cancelado'),
        ('refund', 'Reembolso'),
    ], string='Estado de pago')
    payment_reference = fields.Char('Referencia de pago')
    comment = fields.Text('Comentario')
    generated_history_id = fields.Many2one(
        'mkp.collection.line.history', string='Línea histórica generada',
        readonly=True, ondelete='restrict'
    )
    company_id = fields.Many2one(
        related='sale_order_id.company_id', store=True, readonly=True
    )
    currency_id = fields.Many2one(
        related='sale_order_id.currency_id', store=True, readonly=True
    )
    imported_by_id = fields.Many2one(
        related='create_uid', string='Importado por', store=True, readonly=True
    )
    imported_at = fields.Datetime(
        related='create_date', string='Fecha de importación', store=True, readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group(
                'mkp_collection_control.group_mkp_collection_operator'):
            raise AccessError(_('Se requiere el permiso Operador de Cobranza MKP.'))
        provided_fields = [set(values) for values in vals_list]
        clean_values = []
        for values in vals_list:
            cleaned = dict(values)
            cleaned.pop('generated_history_id', None)
            clean_values.append(cleaned)
        rows = super().create(clean_values)
        for row, fields_present in zip(rows, provided_fields):
            revision = row._apply_import(fields_present)
            row.sudo().with_context(mkp_internal_import=True).write({
                'generated_history_id': revision.id,
            })
        return rows

    def write(self, vals):
        if self.env.su and self.env.context.get('mkp_internal_import'):
            if set(vals) <= {'generated_history_id'}:
                return super().write(vals)
        raise UserError(_('Los registros importados no se modifican.'))

    def unlink(self):
        raise UserError(_('Los registros importados no se eliminan.'))

    def _ensure_collection(self):
        self.ensure_one()
        sale_order = self.sale_order_id
        sale_order.read(['name', 'company_id', 'currency_id'])
        collection = self.env['mkp.collection.order'].search([
            ('sale_order_id', '=', sale_order.id)
        ], limit=1)
        marketplace = sale_order._mkp_field_as_text(
            'x_studio_canal_de_venta_1'
        ).strip()
        marketplace_reference = sale_order._mkp_field_as_text(
            'x_studio_nmero_de_orden_mkp'
        ).strip()
        if not collection:
            collection = self.env['mkp.collection.order'].sudo().create({
                'sale_order_id': sale_order.id,
                'marketplace': marketplace,
                'marketplace_reference': marketplace_reference,
            })
        self.env['mkp.collection.line.history']._sync_sale_order(
            sale_order, collection
        )
        return collection

    def _apply_import(self, provided_fields):
        self.ensure_one()
        collection = self._ensure_collection()
        domain = [
            ('order_id', '=', collection.id),
            ('is_active_revision', '=', True),
            ('sku', '=ilike', (self.sku or '').strip()),
        ]
        if self.line_sequence:
            domain.append(('sequence', '=', self.line_sequence))
        candidates = self.env['mkp.collection.line.history'].search(domain)
        if not candidates:
            raise ValidationError(_(
                'No se encontró una línea activa para la orden %s y el SKU %s.'
            ) % (self.sale_order_id.display_name, self.sku))
        if len(candidates) > 1:
            raise ValidationError(_(
                'El SKU %s aparece más de una vez. Incluya la columna Secuencia de línea.'
            ) % self.sku)
        changes = {
            field_name: self[field_name]
            for field_name in MONETARY_REVISION_FIELDS
            if field_name in provided_fields
        }
        for field_name in ('calculation_type', 'payment_status'):
            if field_name in provided_fields and self[field_name]:
                changes[field_name] = self[field_name]
        if 'payment_reference' in provided_fields:
            changes['payment_reference'] = self.payment_reference or False
        if not changes:
            raise ValidationError(_(
                'La fila no contiene columnas de comisiones, tipo de cálculo, estado o referencia de pago.'
            ))
        return candidates._create_revision(
            changes,
            change_origin='import',
            comment=self.comment or _('Actualización mediante importación.'),
        )
