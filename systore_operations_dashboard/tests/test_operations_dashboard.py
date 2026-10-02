from datetime import datetime

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

from ..models.date_policy import local_day_bounds


@tagged('post_install', '-at_install')
class TestOperationsDashboard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env, login='systore_operator_test',
                                 groups='stock.group_stock_user', tz='America/Mexico_City')
        cls.other_user = new_test_user(cls.env, login='systore_unassigned_test',
                                       groups='stock.group_stock_user', tz='America/Mexico_City')
        cls.warehouse = cls.env['stock.warehouse'].create({
            'name': 'Tablero prueba', 'code': 'SODT', 'reception_steps': 'two_steps',
            'delivery_steps': 'pick_pack_ship', 'systore_operations_enabled': True,
            'systore_operations_user_ids': [Command.set(cls.user.ids)],
        })
        cls.vendor = cls.env['res.partner'].create({'name': 'Proveedor prueba tablero'})
        cls.product = cls.env['product.product'].create({
            'name': 'Producto tablero', 'type': 'consu', 'is_storable': True,
        })
        cls.service = cls.env['systore.operations.dashboard'].with_user(cls.user).with_context(tz=cls.user.tz)

    def make_order(self, packages=7, date='2026-10-01 18:00:00'):
        order = self.env['purchase.order'].create({
            'partner_id': self.vendor.id, 'picking_type_id': self.warehouse.in_type_id.id,
            'systore_expected_packages': packages,
            'order_line': [Command.create({
                'name': self.product.name, 'product_id': self.product.id,
                'product_qty': 10, 'product_uom': self.product.uom_id.id,
                'price_unit': 20, 'date_planned': date,
            })],
        })
        order.button_confirm()
        return order

    def receipt_section(self, date='2026-10-01', scope='date'):
        data = self.service.get_dashboard(self.warehouse.id, date, scope)
        return next(section for section in data['sections'] if section['key'] == 'in')

    def test_two_step_receipt_counts_packages_once(self):
        order = self.make_order()
        self.env.flush_all()
        pickings = self.env['stock.picking'].search([
            ('systore_operations_purchase_ids', 'in', order.ids), ('state', 'not in', ['done', 'cancel']),
        ])
        self.assertGreaterEqual(len(pickings), 2)
        section = self.receipt_section()
        self.assertEqual(section['selected']['orders'], 1)
        self.assertEqual(section['selected']['packages'], 7)
        self.assertEqual(len(section['rows']), 1)
        self.assertEqual(section['rows'][0]['operations'], len(pickings.filtered(lambda p: p.picking_type_id == self.warehouse.in_type_id)))
        storage = next(s for s in self.service.get_dashboard(self.warehouse.id, '2026-10-01')['sections'] if s['key'] == 'storage')
        self.assertEqual(storage['selected']['packages'], 7)
        self.assertEqual(storage['selected']['pieces'], 10)
        self.assertEqual(section['selected']['pieces'], 10)

    def test_expected_date_change_and_negative_packages(self):
        order = self.make_order()
        order.order_line.write({'date_planned': '2026-10-02 18:00:00'})
        self.assertEqual(self.receipt_section()['selected']['orders'], 0)
        self.assertEqual(self.receipt_section('2026-10-02')['selected']['packages'], 7)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            order.systore_expected_packages = -1

    def test_disabled_and_unassigned_warehouse_are_denied(self):
        unassigned = self.service.with_user(self.other_user)
        self.assertFalse(unassigned.get_configuration()['warehouses'])
        with self.assertRaises(AccessError):
            unassigned.get_dashboard(self.warehouse.id)
        with self.assertRaises(AccessError):
            unassigned.open_operations(self.warehouse.id, 'in')
        self.warehouse.systore_operations_enabled = False
        with self.assertRaises(AccessError):
            self.service.get_dashboard(self.warehouse.id)

    def test_configuration_cannot_be_changed_by_operator(self):
        with self.assertRaises(AccessError):
            self.warehouse.with_user(self.user).write({'systore_operations_enabled': False})
        with self.assertRaises(AccessError):
            self.warehouse.with_user(self.user).write({'systore_operations_user_ids': [Command.clear()]})

    def test_native_operation_action_and_forged_id(self):
        order = self.make_order()
        action = self.service.open_operations(self.warehouse.id, 'in', '2026-10-01', 'date', order.id)
        self.assertEqual(action['res_model'], 'stock.picking')
        self.assertEqual(action['views'][-1], (False, 'form'))
        with self.assertRaises(AccessError):
            self.service.open_operations(self.warehouse.id, 'in', '2026-10-01',
                                         'date', order.id, 2147483647)

    def test_inventory_operator_can_read_po_summary_without_purchase_group(self):
        self.assertFalse(self.user.has_group('purchase.group_purchase_user'))
        self.make_order(11)
        section = self.receipt_section()
        self.assertEqual(section['selected']['packages'], 11)
        self.assertTrue(section['rows'][0]['label'].startswith('P'))

    def test_transfer_source_and_dispatch_steps(self):
        customer = self.env.ref('stock.stock_location_customers')
        picking_model = self.env['stock.picking']
        dispatch_pick = picking_model.create({
            'picking_type_id': self.warehouse.pick_type_id.id,
            'location_id': self.warehouse.lot_stock_id.id,
            'location_dest_id': self.warehouse.wh_pack_stock_loc_id.id,
            'scheduled_date': '2026-10-01 18:00:00',
        })
        dispatch_out = picking_model.create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.warehouse.wh_output_stock_loc_id.id,
            'location_dest_id': customer.id,
            'scheduled_date': '2026-10-01 18:00:00',
        })
        transfer = self.service.open_operations(self.warehouse.id, 'transfers', '2026-10-01')
        transfer_ids = picking_model.search(transfer['domain']).ids
        self.assertIn(dispatch_pick.id, transfer_ids)
        self.assertNotIn(dispatch_out.id, transfer_ids)
        recoleccion = self.service.open_operations(self.warehouse.id, 'pick', '2026-10-01')
        self.assertNotIn(dispatch_pick.id, picking_model.search(recoleccion['domain']).ids)  # Borrador excluido de Pick
        salida = self.service.open_operations(self.warehouse.id, 'out', '2026-10-01')
        self.assertIn(dispatch_out.id, picking_model.search(salida['domain']).ids)
        self.assertNotIn(dispatch_pick.id, picking_model.search(salida['domain']).ids)

    def test_supplier_reference_and_unique_pieces(self):
        order = self.make_order()
        order.partner_ref = 'FACT-PROV-123'
        section = self.receipt_section()
        self.assertEqual(section['rows'][0]['supplier_ref'], 'FACT-PROV-123')
        self.assertEqual(section['rows'][0]['pieces'], 10)
        self.assertEqual(section['selected']['pieces'], 10)

    def test_checkboxes_exclude_operation_types(self):
        self.make_order()
        self.warehouse.systore_operations_type_ids = self.warehouse.store_type_id
        data = self.service.get_dashboard(self.warehouse.id, '2026-10-01')
        self.assertEqual([s['key'] for s in data['sections']], ['storage', 'transfers'])
        self.assertEqual(data['sections'][0]['selected']['pieces'], 10)
        action = self.service.open_operations(self.warehouse.id, 'storage', '2026-10-01')
        self.assertEqual(self.env['stock.picking'].search(action['domain']).picking_type_id, self.warehouse.store_type_id)
        self.warehouse.systore_operations_type_ids = False
        self.assertEqual(self.service._visible_sections(self.warehouse), ['transfers'])

    def test_sale_reference_on_all_shipping_steps(self):
        sale = self.env['sale.order'].create({
            'partner_id': self.vendor.id, 'warehouse_id': self.warehouse.id,
            'order_line': [Command.create({'product_id': self.product.id,
                                         'product_uom_qty': 2, 'price_unit': 50})],
        })
        sale.action_confirm()
        self.assertGreaterEqual(len(sale.picking_ids), 3)
        for picking in sale.picking_ids:
            self.assertIn(sale.name, picking.systore_operations_sale_names)

    def test_date_bounds_timezone(self):
        start, end = local_day_bounds(fields.Date.to_date('2026-10-01'), 'America/Mexico_City')
        self.assertEqual(start, datetime(2026, 10, 1, 6))
        self.assertEqual(end, datetime(2026, 10, 2, 6))

    def test_guided_three_steps_and_scanned_delivery(self):
        """Run in Odoo.sh: native reservation, UPC, series, guide and delivery."""
        company = self.warehouse.company_id
        company.systore_upc_validation_warehouse_ids |= self.warehouse
        self.warehouse.pick_type_id.systore_require_upc_on_picking = True
        self.warehouse.pack_type_id.systore_require_tracking_on_pack = True
        self.warehouse.out_type_id.write({'systore_require_upc_on_picking': False,
                                         'systore_require_tracking_on_pack': False})
        self.product.barcode = 'SOD-UPC-TEST'
        self.env['stock.quant']._update_available_quantity(self.product, self.warehouse.lot_stock_id, 5)
        sale = self.env['sale.order'].create({
            'partner_id': self.vendor.id, 'warehouse_id': self.warehouse.id,
            'order_line': [Command.create({'product_id': self.product.id,
                                          'product_uom_qty': 2, 'price_unit': 50})],
        })
        sale.action_confirm()
        pick = sale.picking_ids.filtered(lambda p: p.picking_type_id == self.warehouse.pick_type_id)
        pick.action_assign()
        batch = self.env['stock.picking.batch'].create({
            'picking_type_id': self.warehouse.pick_type_id.id,
            'picking_ids': [Command.set(pick.ids)],
        })
        action = self.service.open_guided_operation(self.warehouse.id, 'pick', scope='all', batch_id=batch.id)
        wizard = self.env['stock.picking.upc.wizard'].with_user(self.user).browse(action['res_id'])
        self.assertEqual(sum(wizard.line_ids.mapped('systore_requested_qty')), 2)
        wizard.line_ids.write({'demand_qty': 2, 'upc_ean': 'WRONG-UPC'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            wizard.action_confirm()
        wizard.line_ids.upc_ean = self.product.barcode
        wizard.action_confirm()
        self.assertEqual(pick.state, 'done')
        pack = sale.picking_ids.filtered(lambda p: p.picking_type_id == self.warehouse.pack_type_id)
        action = self.service.open_guided_operation(self.warehouse.id, 'pack', scope='all', picking_id=pack.id)
        wizard = self.env['stock.picking.upc.wizard'].with_user(self.user).browse(action['res_id'])
        for number, line in enumerate(wizard.line_ids):
            line.write({'upc_ean': self.product.barcode, 'serial_imei': 'SOD-SERIAL-%s' % number})
        wizard.tracking_ref = 'SOD-GUIDE-TEST'
        wizard.action_confirm()
        self.assertEqual(pack.state, 'done')
        self.assertEqual(len(pack.move_line_ids.serial_captured_ids), 2)
        out = sale.picking_ids.filtered(lambda p: p.picking_type_id == self.warehouse.out_type_id)
        action = self.service.open_guided_operation(self.warehouse.id, 'out', scope='all', picking_id=out.id)
        session = self.env['systore.operations.dispatch.session'].with_user(self.user).browse(action['params']['session_id'])
        self.assertEqual(session.get_snapshot()['scanned'], 0)
        with self.assertRaises(UserError), self.cr.savepoint():
            session.scan_package('FOREIGN-GUIDE')
        result = session.scan_package('SOD-GUIDE-TEST')
        self.assertEqual(result['snapshot']['scanned'], 1)
        self.assertEqual(out.state, 'done')
        self.assertEqual(result['snapshot']['validated'], 1)
        with self.assertRaises(UserError), self.cr.savepoint():
            session.scan_package('SOD-GUIDE-TEST')

    def test_receipt_stage_visibility_follows_native_steps(self):
        self.assertIn('storage', self.service._visible_sections(self.warehouse))
        self.warehouse.reception_steps = 'one_step'
        self.assertIn('in', self.service._visible_sections(self.warehouse))
        self.assertNotIn('storage', self.service._visible_sections(self.warehouse))

    def test_mobile_grouped_batch_upc_and_no_serial_capture(self):
        self.warehouse.company_id.systore_upc_validation_warehouse_ids |= self.warehouse
        self.warehouse.pick_type_id.write({'systore_require_upc_on_picking': True,
                                          'systore_require_tracking_on_pack': False})
        self.product.barcode = 'SOD-MOBILE-UPC'
        self.env['stock.quant']._update_available_quantity(self.product, self.warehouse.lot_stock_id, 8)
        picks = self.env['stock.picking']
        for quantity in (1, 2):
            sale = self.env['sale.order'].create({
                'partner_id': self.vendor.id, 'warehouse_id': self.warehouse.id,
                'order_line': [Command.create({'product_id': self.product.id,
                                              'product_uom_qty': quantity, 'price_unit': 50})],
            })
            sale.action_confirm()
            picks |= sale.picking_ids.filtered(lambda p: p.picking_type_id == self.warehouse.pick_type_id)
        picks.action_assign()
        batch = self.env['stock.picking.batch'].create({
            'picking_type_id': self.warehouse.pick_type_id.id, 'picking_ids': [Command.set(picks.ids)]})
        panel = self.service.get_mobile_pick_panel(self.warehouse.id, scope='all', mode='batches')
        card = next(c for c in panel['cards'] if c['batch_id'] == batch.id)
        self.assertEqual(card['orders'], 2)
        self.assertEqual(card['pieces'], 3)
        self.assertEqual(set(card['origins']), set(picks.mapped('origin')))
        detail = self.service.get_mobile_pick_detail(self.warehouse.id, batch_id=batch.id)
        self.assertTrue(detail['can_validate'], detail['notice'])
        self.assertEqual(len(detail['rows']), 1)
        self.assertEqual(detail['rows'][0]['qty'], 3)
        self.assertEqual(set(detail['rows'][0]['picking_ids']), set(picks.ids))
        individual = self.service.get_mobile_pick_detail(self.warehouse.id, picking_id=picks[0].id)
        self.assertFalse(individual['card']['is_batch'])
        self.assertEqual(individual['card']['picking_id'], picks[0].id)
        self.assertEqual(sum(row['qty'] for row in individual['rows']), picks[0].move_ids.product_uom_qty)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.service.check_mobile_pick_upc(self.warehouse.id, False, batch.id,
                                               detail['token'], self.product.id, 'WRONG')
        checked = self.service.check_mobile_pick_upc(self.warehouse.id, False, batch.id,
                                                     detail['token'], self.product.id, self.product.barcode)
        self.assertTrue(checked['valid'])
        self.assertTrue(all(p.state == 'assigned' for p in picks))
        self.assertFalse(any(p.systore_upc_picking_validated for p in picks))
        captures = [{'id': r['id'], 'upc': 'WRONG'} for r in detail['rows']]
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.service.validate_mobile_pick(self.warehouse.id, False, batch.id, detail['token'], captures)
        self.assertFalse(picks.move_line_ids.serial_captured_ids)
        for capture in captures:
            capture['upc'] = self.product.barcode
        result = self.service.validate_mobile_pick(self.warehouse.id, False, batch.id, detail['token'], captures)
        self.assertTrue(result['complete'])
        self.assertTrue(all(p.state == 'done' for p in picks))
        self.assertFalse(picks.move_line_ids.serial_captured_ids)
        self.assertEqual(self.service.open_mobile_pick(self.warehouse.id)['tag'],
                         'systore_operations_dashboard.mobile_pick')

    def test_mobile_panel_denies_unassigned_operator(self):
        with self.assertRaises(AccessError):
            self.service.with_user(self.other_user).get_mobile_pick_panel(self.warehouse.id, scope='all')
