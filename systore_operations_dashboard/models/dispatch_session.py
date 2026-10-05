from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv.expression import AND
from odoo.tools.float_utils import float_compare


class DispatchSession(models.TransientModel):
    _name = 'systore.operations.dispatch.session'
    _description = 'Sesión de escaneo de paquetes de salida'

    warehouse_id = fields.Many2one('stock.warehouse', required=True, readonly=True)
    picking_ids = fields.Many2many('stock.picking', 'systore_dispatch_session_picking_rel',
                                   'session_id', 'picking_id', readonly=True)
    scan_ids = fields.One2many('systore.operations.dispatch.scan', 'session_id', readonly=True)

    def _check_session(self, lock=False):
        self.ensure_one()
        self.check_access('write')
        if self.create_uid != self.env.user:
            raise AccessError(_('Esta sesión pertenece a otro operador.'))
        self.env['systore.operations.dashboard']._warehouse(self.warehouse_id.id)
        if lock:
            self.env.cr.execute('SELECT id FROM systore_operations_dispatch_session WHERE id = %s FOR UPDATE', (self.id,))
            self.invalidate_recordset(['scan_ids'])

    def _pending_pickings(self):
        return self.env['stock.picking'].search(AND([
            self.env['systore.operations.dashboard']._section_domain(self.warehouse_id, 'out'),
            [('id', 'in', self.picking_ids.ids)],
        ]))

    def _packages(self, picking):
        packages = self.env['stock.quant.package']
        loose = False
        for line in picking.move_line_ids.filtered(lambda line: line.state != 'cancel' and line.quantity > 0):
            package = line.result_package_id or line.package_id
            if package:
                packages |= package
            else:
                loose = True
        if packages and loose:
            raise UserError(_('La salida %s contiene piezas sin paquete. Complete el empaque antes de escanear su entrega.') % picking.name)
        return packages

    def _expected_keys(self, picking):
        packages = self._packages(picking)
        if packages:
            return {'pkg:%s' % package.id for package in packages}
        if (picking.carrier_tracking_ref or '').strip():
            return {'guide:%s' % picking.id}
        raise UserError(_('La salida %s no tiene paquetes nativos ni número de guía. Complete el empaque primero.') % picking.name)

    def _complete_pickings(self):
        pending = self._pending_pickings()
        complete = self.env['stock.picking']
        for picking in pending:
            scanned_keys = set(self.scan_ids.filtered(lambda scan: picking in scan.picking_ids).mapped('canonical_key'))
            if scanned_keys and self._expected_keys(picking).issubset(scanned_keys):
                complete |= picking
        return complete

    def _validate_complete(self):
        pickings = self._complete_pickings()
        if not pickings:
            return False
        pickings.check_access('write')
        self.env.cr.execute('SELECT id FROM stock_picking WHERE id IN %s ORDER BY id FOR UPDATE', (tuple(pickings.ids),))
        pickings.invalidate_recordset(['state'])
        pickings = pickings.filtered(lambda picking: picking.state not in ('done', 'cancel'))
        for picking in pickings:
            demand, ready = picking._systore_batch_demand_ready_qty()
            if picking.state != 'assigned' or float_compare(ready, demand, precision_rounding=0.00001) < 0:
                raise UserError(_('La salida %s no está completamente lista. Valide las etapas anteriores y revise la reserva.') % picking.name)
        # Never bypass UPC, tracking, serial/lot or backorder hooks.
        result = pickings.button_validate() if pickings else False
        return result if isinstance(result, dict) else False

    def get_snapshot(self):
        self._check_session()
        self.picking_ids.check_access('read')
        rows = []
        for scan in self.scan_ids.sorted('id'):
            rows.append({'id': scan.id, 'code': scan.scanned_code,
                         'orders': ', '.join(sorted(set(filter(None, scan.picking_ids.mapped('systore_operations_sale_names'))))),
                         'operations': ', '.join(scan.picking_ids.mapped('name')),
                         'removable': not any(p.state == 'done' for p in scan.picking_ids),
                         'validated': bool(scan.picking_ids) and all(p.state == 'done' for p in scan.picking_ids)})
        return {'warehouse': self.warehouse_id.name, 'scanned': len(rows),
                'validated': len(self.picking_ids.filtered(lambda p: p.state == 'done')),
                'rows': rows}

    def scan_package(self, code):
        self._check_session(lock=True)
        if not isinstance(code, str) or not code.strip() or len(code) > 256:
            raise ValidationError(_('Escanee un código de paquete o guía válido.'))
        code = code.strip()
        matches = {}
        for picking in self._pending_pickings():
            names = (picking.move_line_ids.package_id | picking.move_line_ids.result_package_id).mapped('name')
            if code not in names and (picking.carrier_tracking_ref or '').strip() != code:
                continue
            packages = self._packages(picking)
            matching_packages = packages.filtered(lambda package: package.name == code)
            if matching_packages:
                for package in matching_packages:
                    key = 'pkg:%s' % package.id
                    matches.setdefault(key, {'package': package, 'pickings': self.env['stock.picking']})
                    matches[key]['pickings'] |= picking
            elif (picking.carrier_tracking_ref or '').strip() == code:
                if len(packages) > 1:
                    raise UserError(_('Esta guía contiene varios paquetes. Escanee el código de cada paquete nativo por separado.'))
                package = packages[:1]
                key = 'pkg:%s' % package.id if package else 'guide:%s' % picking.id
                matches.setdefault(key, {'package': package, 'pickings': self.env['stock.picking']})
                matches[key]['pickings'] |= picking
        if not matches:
            raise UserError(_('El código no corresponde a una salida pendiente de esta sesión, o ya fue entregado.'))
        if len(matches) != 1:
            raise UserError(_('El código identifica más de un paquete o salida. Use un identificador único.'))
        key, match = next(iter(matches.items()))
        if self.scan_ids.filtered(lambda scan: scan.canonical_key == key):
            raise UserError(_('Este paquete ya fue escaneado en la sesión.'))
        if any(p.state != 'assigned' for p in match['pickings']):
            raise UserError(_('Complete la preparación y reserva de las salidas antes de escanear sus paquetes.'))
        self.env['systore.operations.dispatch.scan'].create({
            'session_id': self.id, 'canonical_key': key, 'scanned_code': code,
            'package_id': match['package'].id or False,
            'picking_ids': [(6, 0, match['pickings'].ids)],
        })
        return {'snapshot': self.get_snapshot(), 'action': False}

    def remove_scan(self, scan_id):
        self._check_session(lock=True)
        if type(scan_id) is not int:
            raise ValidationError(_('Registro inválido.'))
        scan = self.scan_ids.filtered(lambda row: row.id == scan_id)
        if not scan:
            raise AccessError(_('El registro no pertenece a esta sesión.'))
        if any(p.state == 'done' for p in scan.picking_ids):
            raise UserError(_('No se puede retirar un paquete ya entregado.'))
        scan.unlink()
        return {'snapshot': self.get_snapshot(), 'action': False}

    def validate_ready(self):
        self._check_session(lock=True)
        action = self._validate_complete()
        return {'snapshot': self.get_snapshot(), 'action': action}


class DispatchScan(models.TransientModel):
    _name = 'systore.operations.dispatch.scan'
    _description = 'Paquete escaneado para entrega'

    session_id = fields.Many2one('systore.operations.dispatch.session', required=True, ondelete='cascade')
    canonical_key = fields.Char(required=True)
    scanned_code = fields.Char(required=True)
    package_id = fields.Many2one('stock.quant.package')
    picking_ids = fields.Many2many('stock.picking', 'systore_dispatch_scan_picking_rel', 'scan_id', 'picking_id')

    _sql_constraints = [('unique_session_package', 'unique(session_id, canonical_key)',
                         'Este paquete ya fue escaneado en la sesión.')]

    @api.constrains('session_id', 'picking_ids')
    def _check_picking_scope(self):
        for scan in self:
            scan.session_id._check_session()
            if not scan.picking_ids or not scan.picking_ids <= scan.session_id.picking_ids:
                raise ValidationError(_('La salida no pertenece a esta sesión de escaneo.'))
