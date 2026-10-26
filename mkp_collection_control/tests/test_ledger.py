"""Pure ledger invariants. Runs without an Odoo DB via unittest."""
import unittest
from ..models.ledger import money, state, net, apply_event, event_deltas


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
