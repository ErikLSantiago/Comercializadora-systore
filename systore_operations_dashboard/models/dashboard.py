from datetime import timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.osv.expression import AND

from .date_policy import SCOPES, local_day_bounds, local_date, matches_scope


SECTIONS = ('receipts', 'transfers', 'dispatches')
TITLES = {'receipts': 'Recepciones', 'transfers': 'Transferencias', 'dispatches': 'Expediciones'}


class OperationsDashboard(models.AbstractModel):
    _name = 'systore.operations.dashboard'
    _description = 'Tablero de operaciones por almacén'

    @api.model
    def _check_user(self):
        if not self.env.user.has_group('stock.group_stock_user'):
            raise AccessError(_('Necesita acceso de usuario de Inventario para utilizar el tablero.'))

    @api.model
    def _warehouse_domain(self):
        self._check_user()
        return [
            ('systore_operations_enabled', '=', True),
            ('systore_operations_user_ids', 'in', [self.env.uid]),
            ('company_id', 'in', self.env.companies.ids),
        ]

    @api.model
    def _warehouse(self, warehouse_id):
        if isinstance(warehouse_id, bool) or not isinstance(warehouse_id, int):
            raise ValidationError(_('Seleccione un almacén válido.'))
        warehouse = self.env['stock.warehouse'].search(
            AND([self._warehouse_domain(), [('id', '=', warehouse_id)]]), limit=1,
        )
        if not warehouse:
            raise AccessError(_('Este almacén no está habilitado o no está asignado a su usuario.'))
        return warehouse

    @api.model
    def _parameters(self, selected_date, scope):
        if scope not in SCOPES:
            raise ValidationError(_('Filtro de fecha inválido.'))
        try:
            day = fields.Date.to_date(selected_date) if selected_date else fields.Date.context_today(self)
        except (ValueError, TypeError):
            raise ValidationError(_('Seleccione una fecha válida.'))
        if not day:
            raise ValidationError(_('Seleccione una fecha válida.'))
        timezone = self.env.context.get('tz') or self.env.user.tz or 'UTC'
        if timezone not in pytz.all_timezones_set:
            timezone = 'UTC'
        return day, fields.Date.context_today(self.with_context(tz=timezone)), timezone

    @api.model
    def _section_domain(self, warehouse, section):
        if section not in SECTIONS:
            raise ValidationError(_('Sección inválida.'))
        common = [
            ('company_id', '=', warehouse.company_id.id),
            ('state', 'not in', ['done', 'cancel']),
        ]
        if section == 'receipts':
            types = (warehouse.in_type_id | warehouse.store_type_id | warehouse.qc_type_id)
            specific = [
                ('picking_type_id', 'in', types.ids),
                ('location_dest_id', 'child_of', warehouse.view_location_id.id),
                ('location_dest_id.usage', 'in', ['internal', 'transit']),
            ]
        elif section == 'transfers':
            # Source criterion intentionally includes native picks and one-step deliveries.
            specific = [
                ('location_id', 'child_of', warehouse.lot_stock_id.id),
                ('location_dest_id', '!=', False),
            ]
        else:
            types = warehouse.out_type_id | warehouse.pick_type_id | warehouse.pack_type_id
            specific = [('picking_type_id', 'in', types.ids)]
        return AND([common, specific])

    @api.model
    def _datetime_domain(self, field, day, scope, today, timezone):
        if scope == 'all':
            return []
        if scope == 'undated':
            return [(field, '=', False)]
        start, end = local_day_bounds(today if scope == 'overdue' else day, timezone)
        if scope == 'overdue':
            return [(field, '<', fields.Datetime.to_string(start))]
        return [(field, '>=', fields.Datetime.to_string(start)),
                (field, '<', fields.Datetime.to_string(end))]

    @api.model
    def _filtered_domain(self, warehouse, section, day, scope, today, timezone):
        base = self._section_domain(warehouse, section)
        if section != 'receipts':
            return AND([base, self._datetime_domain('scheduled_date', day, scope, today, timezone)])
        # Filter exact operational metadata from readable pickings. A relational
        # date domain would require Purchase ACLs and may combine date bounds
        # from different POs in a consolidated picking.
        pickings = self.env['stock.picking'].search(base)
        entries = self._receipt_entries(pickings)
        ids = {pid for entry in entries
               if matches_scope(entry['date'], scope, day, today, timezone)
               for pid in entry['picking_ids']}
        return AND([base, [('id', 'in', sorted(ids))]])

    @api.model
    def get_configuration(self):
        warehouses = self.env['stock.warehouse'].search(self._warehouse_domain(), order='sequence, name, id')
        return {
            'today': fields.Date.to_string(fields.Date.context_today(self)),
            'warehouses': [{'id': wh.id, 'name': wh.name, 'code': wh.code,
                            'company': wh.company_id.name} for wh in warehouses],
        }

    @api.model
    def _receipt_entries(self, pickings):
        # Elevation is limited to operational PO metadata linked to readable pickings.
        # Inventory operators do not need access to purchase costs or the Purchase app.
        ids = pickings.sudo().mapped('systore_operations_purchase_ids').ids
        values = self.env['purchase.order'].sudo().browse(ids).read(
            ['name', 'partner_id', 'date_planned', 'systore_expected_packages'],
        )
        order_values = {item['id']: item for item in values}
        entries = {}
        for picking in pickings:
            po_ids = picking.sudo().systore_operations_purchase_ids.ids
            if not po_ids:
                entries['p%s' % picking.id] = {
                    'key': 'p%s' % picking.id, 'purchase_id': False,
                    'label': picking.name, 'partner': picking.partner_id.display_name or '',
                    'date': picking.scheduled_date, 'packages': 0, 'picking_ids': [picking.id],
                }
            for po_id in po_ids:
                key = 'o%s' % po_id
                if key not in entries:
                    item = order_values[po_id]
                    entries[key] = {
                        'key': key, 'purchase_id': po_id, 'label': item['name'],
                        'partner': item['partner_id'][1] if item['partner_id'] else '',
                        'date': fields.Datetime.to_datetime(item['date_planned']),
                        'packages': item['systore_expected_packages'], 'picking_ids': [],
                    }
                entries[key]['picking_ids'].append(picking.id)
        return list(entries.values())

    @api.model
    def _totals(self, entries):
        return {
            'orders': sum(bool(entry.get('purchase_id')) for entry in entries),
            'packages': sum(entry.get('packages', 0) for entry in entries),
            'operations': len({pid for entry in entries for pid in entry['picking_ids']}),
        }

    @api.model
    def get_dashboard(self, warehouse_id, selected_date=False, scope='date'):
        warehouse = self._warehouse(warehouse_id)
        day, today, timezone = self._parameters(selected_date, scope)
        sections = []
        for section in SECTIONS:
            pickings = self.env['stock.picking'].search(self._section_domain(warehouse, section),
                                                       order='scheduled_date, id')
            pickings.fetch(['name', 'scheduled_date', 'state', 'partner_id', 'picking_type_id',
                            'location_id', 'location_dest_id'])
            if section == 'receipts':
                entries = self._receipt_entries(pickings)
            else:
                entries = [{'key': 'p%s' % p.id, 'purchase_id': False, 'label': p.name,
                            'date': p.scheduled_date, 'picking_ids': [p.id]} for p in pickings]
            selected = [e for e in entries if matches_scope(e['date'], scope, day, today, timezone)]
            def count_for(count_day, count_scope='date'):
                return self._totals([e for e in entries
                                     if matches_scope(e['date'], count_scope, count_day, today, timezone)])
            rows = []
            if section == 'receipts':
                selected.sort(key=lambda e: (e['date'] or fields.Datetime.to_datetime('9999-01-01'), e['label']))
                for entry in selected[:60]:
                    rows.append({
                        'key': entry['key'], 'purchase_id': entry['purchase_id'],
                        'label': entry['label'], 'partner': entry['partner'],
                        'date': fields.Date.to_string(local_date(entry['date'], timezone)),
                        'packages': entry['packages'], 'operations': len(entry['picking_ids']),
                        'picking_id': entry['picking_ids'][0] if len(entry['picking_ids']) == 1 else False,
                    })
            else:
                selected_ids = {pid for e in selected for pid in e['picking_ids']}
                for picking in pickings.filtered(lambda p: p.id in selected_ids)[:60]:
                    rows.append({
                        'key': 'p%s' % picking.id, 'label': picking.name, 'picking_id': picking.id,
                        'type': picking.picking_type_id.name, 'state': picking.state,
                        'date': fields.Date.to_string(local_date(picking.scheduled_date, timezone)),
                        'source': picking.location_id.display_name,
                        'destination': picking.location_dest_id.display_name,
                    })
            sections.append({
                'key': section, 'title': TITLES[section], 'selected': self._totals(selected),
                'today': count_for(today), 'tomorrow': count_for(today + timedelta(days=1)),
                'overdue': count_for(today, 'overdue'), 'undated': count_for(today, 'undated'),
                'rows': rows, 'truncated': len(selected) > 60,
            })
        return {'sections': sections, 'selected_date': fields.Date.to_string(day),
                'today': fields.Date.to_string(today), 'stock_location': warehouse.lot_stock_id.display_name}

    @api.model
    def open_operations(self, warehouse_id, section, selected_date=False, scope='date',
                        purchase_id=False, picking_id=False):
        warehouse = self._warehouse(warehouse_id)
        day, today, timezone = self._parameters(selected_date, scope)
        domain = self._filtered_domain(warehouse, section, day, scope, today, timezone)
        if purchase_id:
            if section != 'receipts' or isinstance(purchase_id, bool) or not isinstance(purchase_id, int):
                raise ValidationError(_('Compra inválida.'))
            domain = AND([domain, [('systore_operations_purchase_ids', 'in', [purchase_id])]])
        action = {
            'type': 'ir.actions.act_window', 'name': TITLES[section], 'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'views': [(self.env.ref('systore_operations_dashboard.view_operations_picking_list').id, 'list'),
                      (False, 'form')],
            'domain': domain, 'target': 'current',
            'context': dict(self.env.context, create=False),
        }
        if picking_id:
            if isinstance(picking_id, bool) or not isinstance(picking_id, int):
                raise ValidationError(_('Operación inválida.'))
            picking = self.env['stock.picking'].search(AND([domain, [('id', '=', picking_id)]]), limit=1)
            if not picking:
                raise AccessError(_('La operación ya no pertenece a este filtro o no está disponible. Actualice el tablero.'))
            action.update({'view_mode': 'form', 'views': [(False, 'form')], 'res_id': picking.id})
        return action
