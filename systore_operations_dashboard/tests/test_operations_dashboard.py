from datetime import datetime

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
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
        return next(section for section in data['sections'] if section['key'] == 'receipts')

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
        self.assertEqual(section['rows'][0]['operations'], len(pickings))
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
            unassigned.open_operations(self.warehouse.id, 'receipts')
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
        action = self.service.open_operations(self.warehouse.id, 'receipts', '2026-10-01', 'date', order.id)
        self.assertEqual(action['res_model'], 'stock.picking')
        self.assertEqual(action['views'][-1], (False, 'form'))
        with self.assertRaises(AccessError):
            self.service.open_operations(self.warehouse.id, 'receipts', '2026-10-01',
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
        self.assertIn(dispatch_pick.id, picking_model.search(recoleccion['domain']).ids)
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
        order = self.make_order()
        self.warehouse.systore_operations_type_ids = self.warehouse.store_type_id
        self.assertEqual(self.receipt_section()['selected']['pieces'], 10)
        action = self.service.open_operations(self.warehouse.id, 'receipts', '2026-10-01')
        pickings = self.env['stock.picking'].search(action['domain'])
        self.assertTrue(pickings)
        self.assertEqual(pickings.picking_type_id, self.warehouse.store_type_id)
        self.assertNotIn('pick', self.service._visible_sections(self.warehouse))
        self.warehouse.systore_operations_type_ids = False
        self.assertEqual(self.receipt_section()['selected']['orders'], 0)
        self.assertEqual(self.service._visible_sections(self.warehouse), ['receipts', 'transfers'])

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
