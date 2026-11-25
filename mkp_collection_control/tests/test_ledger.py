"""Pure ledger invariants. Runs without an Odoo DB via unittest."""
import unittest
from ..models.ledger import (
    money, state, net, apply_event, event_deltas, snapshot_deltas, payment_deltas,
    collection_commission_totals, collection_line_balance, collection_line_totals,
    validate_return_quantity, wholesale_order_totals,
)


class TestMkpCollectionLedger(unittest.TestCase):
    def post(self, current, kind, **kwargs):
        return apply_event(current, event_deltas(kind, **kwargs))

    def opening(self):
        return self.post(state(), 'opening', gross=5499, withholding=497.75,
                         commission=549.9, shipping=100)

    def test_opening_partial_payment_and_release(self):
        x = self.opening()
        self.assertEqual(x['pending'], money('4351.35'))
        x = self.post(x, 'hold', amount=1500)
        self.assertEqual(x['held'], money(1500))
        self.assertEqual(x['pending'], money('2851.35'))
        x = self.post(x, 'release', amount=1500)
        self.assertEqual(x['held'], money(0))
        self.assertEqual(x['released'], money(1500))
        x = self.post(x, 'payment', amount=1500)
        self.assertEqual(x['paid'], money(1500))
        self.assertEqual(net(x), money('4351.35'))

    def test_coupon_and_killer_commissions(self):
        x = self.opening()
        x = self.post(x, 'coupon', amount=500, extra_commission=50)
        x = self.post(x, 'killer', amount=1000, extra_commission=100)
        self.assertEqual(x['gross'], money(6999))
        self.assertEqual(x['commission'], money('699.90'))
        self.assertEqual(x['pending'], money('5701.35'))

    def test_refund_plus_one_guide_as_other_fees(self):
        x = self.coupon_killer_state()
        x = self.post(x, 'refund', amount='5701.35', bucket='pending')
        self.assertEqual(net(x), money(0))
        x = self.post(x, 'other', amount=100)
        self.assertEqual(x['pending'], money(-100))
        self.assertEqual(net(x), money(-100))
        self.assertEqual(x['refunded'], money('5701.35'))

    def coupon_killer_state(self):
        x = self.opening()
        x = self.post(x, 'coupon', amount=500, extra_commission=50)
        return self.post(x, 'killer', amount=1000, extra_commission=100)

    def test_reversal_recovers_before_state(self):
        x = self.opening()
        delta = event_deltas('coupon', amount=500, extra_commission=50)
        advanced = apply_event(x, delta)
        restored = apply_event(advanced, {k: -v for k, v in delta.items()})
        self.assertEqual(x, restored)

    def test_unsupported_overrelease(self):
        with self.assertRaises(ValueError):
            self.post(self.opening(), 'release', amount=1000)

    def test_unsupported_overrefund(self):
        with self.assertRaises(ValueError):
            self.post(self.opening(), 'refund', amount=100, bucket='held')


    def test_cannot_reverse_retention_after_release_without_reverting_release(self):
        x = self.opening()
        retention = event_deltas('hold', amount=1500)
        x = apply_event(x, retention)
        x = self.post(x, 'release', amount=1500)
        with self.assertRaises(ValueError):
            apply_event(x, {k: -v for k, v in retention.items()})

    def test_fee_reduction_and_payment_refund(self):
        x = self.opening()
        x = self.post(x, 'commission', amount=-10)
        self.assertEqual(net(x), money('4361.35'))
        x = self.post(x, 'release_direct', amount=1500)
        x = self.post(x, 'payment', amount=1500)
        x = self.post(x, 'refund', amount=1500, bucket='paid')
        self.assertEqual(x['paid'], money(0))
        self.assertEqual(x['refunded'], money(1500))
        self.assertEqual(net(x), money('2861.35'))

    def test_underflow_before_opening(self):
        with self.assertRaises(ValueError):
            self.post(state(), 'opening', gross=100, commission=200)

    def test_state_snapshot_and_separate_commissions(self):
        current = state()
        current = apply_event(current, snapshot_deltas(
            current,
            gross=1000,
            coupon_amount=100,
            killer_amount=50,
            withholding=100,
            commission=80,
            killer_commission=20,
            coupon_commission=10,
            shipping=50,
            other=5,
        ))
        self.assertEqual(current['pending'], money(685))
        self.assertEqual(net(current), money(685))

        recalculated = apply_event(current, snapshot_deltas(
            current,
            gross=1100,
            coupon_amount=100,
            killer_amount=50,
            withholding=100,
            commission=90,
            killer_commission=25,
            coupon_commission=15,
            shipping=50,
            other=5,
        ))
        self.assertEqual(recalculated['pending'], money(765))
        self.assertEqual(net(recalculated), money(765))

    def test_collection_revisions_and_refund(self):
        current = apply_event(state(), snapshot_deltas(state(), gross=1000))
        deltas = payment_deltas(current, [
            {'amount': 100, 'payment_status': 'held'},
            {'amount': 200, 'payment_status': 'paid'},
            {'amount': 30, 'payment_status': 'refund'},
            {'amount': 50, 'payment_status': 'cancelled'},
        ])
        current = apply_event(current, deltas)
        self.assertEqual(current['pending'], money(670))
        self.assertEqual(current['held'], money(100))
        self.assertEqual(current['paid'], money(200))
        self.assertEqual(current['refunded'], money(30))
        self.assertEqual(net(current), money(970))

        revision = payment_deltas(current, [{
            'source_payment_id': 1,
            'old_amount': 100,
            'old_payment_status': 'held',
            'amount': 120,
            'payment_status': 'paid',
        }])
        current = apply_event(current, revision)
        self.assertEqual(current['pending'], money(650))
        self.assertEqual(current['held'], money(0))
        self.assertEqual(current['paid'], money(320))

        with self.assertRaises(ValueError):
            payment_deltas(current, [{'amount': 0, 'payment_status': 'pending'}])

    def test_collection_line_totals(self):
        subtotal, adjusted = collection_line_totals(
            amount=1000,
            coupon_amount=100,
            killer_amount=50,
            killer_commission=20,
            commission=80,
            taxes=100,
            shipping=50,
            other_commission=5,
        )
        self.assertEqual(subtotal, money(950))
        self.assertEqual(adjusted, money(695))

    def test_commissions_are_extended_by_sold_pieces(self):
        killer_total, commission_total, other_total = collection_commission_totals(
            quantity=3,
            killer_commission=20,
            commission=80,
            other_commission=5,
        )
        self.assertEqual(killer_total, money(60))
        self.assertEqual(commission_total, money(240))
        self.assertEqual(other_total, money(15))
        subtotal, adjusted = collection_line_totals(
            amount=1000,
            quantity=3,
            coupon_amount=100,
            killer_amount=50,
            killer_commission=20,
            commission=80,
            taxes=100,
            shipping=50,
            other_commission=5,
        )
        self.assertEqual(subtotal, money(950))
        self.assertEqual(adjusted, money(485))

    def test_commission_multiplier_uses_absolute_quantity(self):
        self.assertEqual(
            collection_commission_totals(quantity=-2, commission=25)[1],
            money(50),
        )

    def test_collection_line_balance_supports_partial_payments(self):
        self.assertEqual(collection_line_balance(695, 200), money(495))
        self.assertEqual(collection_line_balance(695, 695), money(0))
        self.assertEqual(collection_line_balance(695, 700), money(-5))

    def test_return_quantity_validation(self):
        self.assertEqual(validate_return_quantity(1, 2, 'created'), 1)
        with self.assertRaises(ValueError):
            validate_return_quantity(-1, 2, 'created')
        with self.assertRaises(ValueError):
            validate_return_quantity(3, 2, 'created')
        with self.assertRaises(ValueError):
            validate_return_quantity(1, 2, 'sale')

    def test_wholesale_order_level_totals(self):
        net_expected, paid, pending, balance = wholesale_order_totals(
            order_total=10000,
            general_expense=750,
            payments=[
                {'amount': 3000, 'payment_status': 'paid'},
                {'amount': 500, 'payment_status': 'refund'},
                {'amount': 1000, 'payment_status': 'pending'},
                {'amount': 200, 'payment_status': 'cancelled'},
            ],
        )
        self.assertEqual(net_expected, money(9250))
        self.assertEqual(paid, money(2500))
        self.assertEqual(pending, money(1000))
        self.assertEqual(balance, money(6750))

    def test_wholesale_signed_discounts_and_adjustments(self):
        net_expected, paid, pending, balance = wholesale_order_totals(
            order_total=10000,
            general_expense=750,
            payments=[
                {'operation_type': 'payment', 'amount': 3000,
                 'payment_status': 'paid'},
                {'operation_type': 'discount', 'amount': -500,
                 'payment_status': 'paid'},
                {'operation_type': 'credit_note', 'amount': -250,
                 'payment_status': 'paid'},
                {'operation_type': 'adjustment', 'amount': 100,
                 'payment_status': 'paid'},
            ],
        )
        self.assertEqual(net_expected, money(8600))
        self.assertEqual(paid, money(3000))
        self.assertEqual(pending, money(0))
        self.assertEqual(balance, money(5600))
