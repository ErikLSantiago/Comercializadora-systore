import base64
import csv
import io
import unicodedata
from decimal import Decimal, InvalidOperation

from odoo import fields, models, _
from odoo.exceptions import AccessError, ValidationError


class MkpCollectionImportWizard(models.TransientModel):
    _name = 'mkp.collection.import.wizard'
    _description = 'Importar registros de cobranza'

    file_data = fields.Binary('Archivo CSV', required=True, attachment=False)
    file_name = fields.Char('Nombre del archivo')

    @staticmethod
    def _normalize(value):
        text = unicodedata.normalize('NFKD', str(value or ''))
        text = ''.join(char for char in text if not unicodedata.combining(char))
        return '_'.join(text.strip().lower().replace('-', ' ').split())

    @classmethod
    def _row_value(cls, row, *names):
        for name in names:
            value = row.get(cls._normalize(name))
            if value not in (None, ''):
                return value
        return ''

    @staticmethod
    def _money(value, label):
        text = str(value or '').strip().replace('$', '').replace(' ', '')
        if not text:
            return 0.0
        if ',' in text and '.' in text:
            text = text.replace(',', '')
        elif ',' in text:
            text = text.replace(',', '.')
        try:
            return float(Decimal(text))
        except InvalidOperation as exc:
            raise ValidationError(_('El valor de %s no es un importe válido: %s') % (label, value)) from exc

    @classmethod
    def _state(cls, value):
        normalized = cls._normalize(value)
        states = {
            'borrador': 'draft',
            'draft': 'draft',
            'confirmado': 'confirmed',
            'confirmed': 'confirmed',
            'recalculado': 'recalculated',
            'recalculated': 'recalculated',
            'devolucion': 'refund',
            'refund': 'refund',
        }
        if normalized not in states:
            raise ValidationError(_('Estado no reconocido: %s') % value)
        return states[normalized]

    @classmethod
    def _refund_bucket(cls, value):
        normalized = cls._normalize(value) or 'monto_por_cobrar'
        buckets = {
            'monto_por_cobrar': 'pending',
            'por_cobrar': 'pending',
            'pending': 'pending',
            'retenido': 'held',
            'held': 'held',
            'liberado': 'released',
            'released': 'released',
            'pago_reportado': 'paid',
            'pagado': 'paid',
            'paid': 'paid',
        }
        if normalized not in buckets:
            raise ValidationError(_('Origen de devolución no reconocido: %s') % value)
        return buckets[normalized]

    def _rows(self):
        try:
            raw = base64.b64decode(self.file_data or b'', validate=True)
            text = raw.decode('utf-8-sig')
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValidationError(_('El archivo debe ser un CSV válido con codificación UTF-8.')) from exc
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=',;\t')
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        if not reader.fieldnames:
            raise ValidationError(_('El archivo CSV no contiene encabezados.'))
        for row in reader:
            yield {self._normalize(key): (value or '').strip() for key, value in row.items() if key}

    def action_import(self):
        self.ensure_one()
        if not self.env.user.has_group('mkp_collection_control.group_mkp_collection_operator'):
            raise AccessError(_('Debe pertenecer al grupo Operador de Cobranza MKP.'))

        imported_event_ids = []
        capture_model = self.env['mkp.collection.capture.wizard']
        for row_number, row in enumerate(self._rows(), start=2):
            try:
                sale_name = self._row_value(row, 'pedido_odoo', 'orden_venta', 'pedido')
                if not sale_name:
                    raise ValidationError(_('Falta Pedido Odoo.'))
                sale = self.env['sale.order'].search([('name', '=', sale_name)], limit=1)
                if not sale:
                    raise ValidationError(_('No existe la orden de venta %s.') % sale_name)
                sale.read(['name', 'amount_total', 'company_id'])

                payment_state = self._state(self._row_value(row, 'estado'))
                gross_raw = self._row_value(row, 'venta')
                if payment_state != 'refund' and gross_raw == '':
                    raise ValidationError(_('Falta Venta para la fotografía financiera.'))
                event_time_raw = self._row_value(row, 'fecha_evento', 'fecha')
                try:
                    event_time = fields.Datetime.to_datetime(
                        event_time_raw.replace('T', ' ') if event_time_raw else fields.Datetime.now()
                    )
                except (TypeError, ValueError) as exc:
                    raise ValidationError(_('Fecha del evento inválida: %s') % event_time_raw) from exc

                collection = self.env['mkp.collection.order'].search([
                    ('sale_order_id', '=', sale.id)], limit=1)
                if not collection:
                    if payment_state == 'refund':
                        raise ValidationError(_('La devolución requiere un expediente previo.'))
                    marketplace = capture_model._get_sale_marketplace(sale)
                    if not marketplace:
                        raise ValidationError(_(
                            'La orden no tiene informado x_studio_canal_de_venta_1.'
                        ))
                    collection = self.env['mkp.collection.order'].sudo().create({
                        'sale_order_id': sale.id,
                        'marketplace': marketplace.strip(),
                        'marketplace_reference': capture_model._get_sale_marketplace_ref(sale).strip(),
                    })

                event = collection._post_event(
                    payment_state=payment_state,
                    event_time=event_time,
                    gross=self._money(gross_raw, 'Venta'),
                    coupon_amount=self._money(self._row_value(row, 'cupon'), 'Cupon'),
                    killer_amount=self._money(self._row_value(row, 'killer'), 'Killer'),
                    withholding=self._money(
                        self._row_value(row, 'retenciones', 'impuestos'), 'Retenciones'
                    ),
                    commission=self._money(self._row_value(row, 'comision'), 'Comisión'),
                    killer_commission=self._money(
                        self._row_value(row, 'comision_killer'), 'Comisión killer'
                    ),
                    coupon_commission=self._money(
                        self._row_value(row, 'comision_cupon'), 'Comisión cupón'
                    ),
                    shipping=self._money(self._row_value(row, 'envio'), 'Envío'),
                    other=self._money(
                        self._row_value(row, 'otras_comisiones'), 'Otras comisiones'
                    ),
                    amount=self._money(
                        self._row_value(row, 'importe_devolucion', 'monto_devolucion'),
                        'Importe devolución',
                    ),
                    bucket=self._refund_bucket(
                        self._row_value(row, 'origen_devolucion')
                    ),
                    reference=self._row_value(row, 'referencia'),
                    notes=self._row_value(row, 'comentario', 'observaciones'),
                )
                imported_event_ids.append(event.id)
            except (AccessError, ValidationError) as exc:
                raise ValidationError(_('Error en la fila %s: %s') % (row_number, exc)) from exc

        if not imported_event_ids:
            raise ValidationError(_('El archivo no contiene registros para importar.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Registros importados'),
            'res_model': 'mkp.collection.event',
            'view_mode': 'list,form',
            'domain': [('id', 'in', imported_event_ids)],
        }
