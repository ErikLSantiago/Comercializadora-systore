"""Pure deterministic MXN-compatible ledger; no Odoo imports.

Each financial event is an immutable signed DELTA, not a replacement snapshot.
'paid' is a payment *reported by the marketplace*, NOT a confirmed bank deposit.
The outstanding/pending bucket can be negative for subsequent marketplace fees.
"""
from decimal import Decimal, ROUND_HALF_UP

KEYS = ('gross', 'coupon_amount', 'killer_amount',
        'withholding', 'commission', 'killer_commission',
        'coupon_commission', 'shipping', 'other',
        'refunded', 'pending', 'held', 'released', 'paid')
BUCKETS = ('pending', 'held', 'released', 'paid')
CENTS = Decimal('0.01')


def money(value):
    return Decimal(str(value or 0)).quantize(CENTS, rounding=ROUND_HALF_UP)


def state(values=None):
    values = values or {}
    return {key: money(values.get(key, 0)) for key in KEYS}


def net(values):
    return money(values['gross'] - values['coupon_amount'] + values['killer_amount']
                 - values['withholding']
                 - values['commission'] - values['killer_commission']
                 - values['coupon_commission'] - values['shipping']
                 - values['other'] - values['refunded'])


def collection_commission_totals(*, quantity=1, killer_commission=0,
                                 commission=0, other_commission=0):
    """Extend per-piece commission values by the absolute sold quantity."""
    pieces = abs(Decimal(str(quantity or 0)))
    return (
        money(money(killer_commission) * pieces),
        money(money(commission) * pieces),
        money(money(other_commission) * pieces),
    )


def collection_line_totals(*, amount=0, quantity=1, coupon_amount=0,
                           killer_amount=0, killer_commission=0, commission=0,
                           taxes=0, shipping=0, other_commission=0):
    """Return totals, extending only commission concepts by sold pieces."""
    subtotal = money(money(amount) - money(coupon_amount) + money(killer_amount))
    killer_total, commission_total, other_total = collection_commission_totals(
        quantity=quantity,
        killer_commission=killer_commission,
        commission=commission,
        other_commission=other_commission,
    )
    adjusted_total = money(
        subtotal
        - killer_total
        - commission_total
        - money(taxes)
        - money(shipping)
        - other_total
    )
    return subtotal, adjusted_total


def collection_line_balance(adjusted_total=0, paid_amount=0):
    """Return the outstanding balance after cumulative partial payments."""
    return money(money(adjusted_total) - money(paid_amount))


def wholesale_order_totals(*, order_total=0, general_expense=0, payments=None):
    """Return net, paid, pending and balance for the order-level wholesale flow."""
    expense = money(general_expense)
    if expense < 0:
        raise ValueError('El gasto general no puede ser negativo.')
    paid = money(0)
    pending = money(0)
    net_adjustments = money(0)
    for payment in payments or []:
        amount = money(payment.get('amount'))
        operation_type = payment.get('operation_type') or 'payment'
        # An inline One2many row exists transiently with amount 0 while the
        # user is still editing it. It must not break the sale order onchange;
        # the model constraint validates the final value when the row is saved.
        if not amount:
            continue
        if operation_type == 'payment' and amount <= 0:
            continue
        if operation_type in ('credit_note', 'discount') and amount >= 0:
            continue
        if operation_type not in (
                'payment', 'credit_note', 'discount', 'adjustment'):
            continue
        status = payment.get('payment_status')
        if status == 'paid' and operation_type == 'payment':
            paid = money(paid + amount)
        elif status == 'paid':
            net_adjustments = money(net_adjustments + amount)
        elif status == 'refund' and operation_type == 'payment':
            paid = money(paid - amount)
        elif status == 'refund':
            net_adjustments = money(net_adjustments - amount)
        elif status in ('held', 'pending'):
            if operation_type == 'payment':
                pending = money(pending + amount)
        elif status != 'cancelled':
            raise ValueError('Estado de pago de mayoreo desconocido.')
    net_expected = money(money(order_total) - expense + net_adjustments)
    return net_expected, paid, pending, money(net_expected - paid)


def wholesale_customer_payment_state(amount_due=0):
    """Classify a wholesale order by its current customer-facing balance."""
    return 'paid' if money(amount_due) <= 0 else 'pending'


def validate_return_quantity(return_quantity, ordered_quantity, return_status='sale'):
    """Validate a product quantity without imposing monetary rounding."""
    quantity = Decimal(str(return_quantity or 0))
    maximum = abs(Decimal(str(ordered_quantity or 0)))
    if quantity < 0:
        raise ValueError('Las piezas devueltas no pueden ser negativas.')
    if quantity > maximum:
        raise ValueError('Las piezas devueltas no pueden superar la cantidad vendida.')
    if return_status == 'sale' and quantity:
        raise ValueError('El estado Venta no admite piezas devueltas.')
    return quantity


def snapshot_deltas(before, *, gross=0, coupon_amount=0, killer_amount=0,
                    withholding=0, commission=0,
                    killer_commission=0, coupon_commission=0,
                    shipping=0, other=0):
    """Build deltas that restate the current commission breakdown.

    Draft, confirmed and recalculated entries all capture a complete financial
    snapshot. The difference in expected net remains in the pending bucket;
    funds already held, released or reported as paid are left untouched.
    """
    old = state(before)
    targets = {
        'gross': money(gross),
        'coupon_amount': money(coupon_amount),
        'killer_amount': money(killer_amount),
        'withholding': money(withholding),
        'commission': money(commission),
        'killer_commission': money(killer_commission),
        'coupon_commission': money(coupon_commission),
        'shipping': money(shipping),
        'other': money(other),
    }
    if any(value < 0 for value in targets.values()):
        raise ValueError('El desglose de comisiones no admite valores negativos.')
    target_net = money(
        targets['gross'] - targets['coupon_amount'] + targets['killer_amount']
        - targets['withholding'] - targets['commission']
        - targets['killer_commission'] - targets['coupon_commission']
        - targets['shipping'] - targets['other'] - old['refunded']
    )
    if target_net < 0 and not old['refunded']:
        raise ValueError('El neto del desglose no puede ser negativo.')
    deltas = state()
    for key, target in targets.items():
        deltas[key] = money(target - old[key])
    deltas['pending'] = money(target_net - net(old))
    return deltas


def _collection_contribution(amount, collection_status):
    """Return the ledger contribution for one active collection revision."""
    value = money(amount)
    if value <= 0:
        raise ValueError('El importe de cobranza debe ser mayor a cero.')
    delta = state()
    if collection_status in ('pending', 'cancelled'):
        return delta
    if collection_status == 'held':
        delta['pending'], delta['held'] = -value, value
    elif collection_status == 'paid':
        delta['pending'], delta['paid'] = -value, value
    elif collection_status == 'refund':
        delta['pending'], delta['refunded'] = -value, value
    else:
        raise ValueError('Estado de cobranza desconocido.')
    return delta


def payment_deltas(before, payments):
    """Aggregate differences between previous and new collection revisions."""
    total = state()
    for payment in payments or []:
        new_delta = _collection_contribution(
            payment.get('amount'), payment.get('payment_status')
        )
        if payment.get('source_payment_id'):
            old_delta = _collection_contribution(
                payment.get('old_amount'), payment.get('old_payment_status')
            )
        else:
            old_delta = state()
        total = {
            key: money(total[key] + new_delta[key] - old_delta[key])
            for key in KEYS
        }
    # Validate the resulting aggregate against the current ledger.
    apply_event(before, total)
    return total


def event_deltas(kind, *, amount=0, extra_commission=0,
                 gross=0, withholding=0, commission=0,
                 killer_commission=0, coupon_commission=0,
                 shipping=0, other=0, bucket='pending'):
    """Return journal deltas for an opening, transfer, adjustment or refund.

    Raises ValueError for unrecognized concepts, unsupported refund buckets,
    nonpositive transfers or unsupported negative amounts.
    """
    a = money(amount)
    c = money(extra_commission)
    d = state()
    if kind == 'opening':
        vals = dict(gross=money(gross), withholding=money(withholding),
                    commission=money(commission),
                    killer_commission=money(killer_commission),
                    coupon_commission=money(coupon_commission),
                    shipping=money(shipping), other=money(other))
        if any(v < 0 for v in vals.values()):
            raise ValueError('El desglose inicial no admite valores negativos.')
        d.update(vals)
        d['pending'] = money(vals['gross'] - vals['withholding']
                             - vals['commission'] - vals['killer_commission']
                             - vals['coupon_commission'] - vals['shipping']
                             - vals['other'])
        if d['pending'] < 0:
            raise ValueError('El neto inicial no puede ser negativo.')
    elif kind in ('hold', 'release', 'unlock', 'release_direct', 'payment'):
        if a <= 0:
            raise ValueError('El importe de transferencia debe ser mayor a cero.')
        src, dst = {
            'hold': ('pending', 'held'),
            'release': ('held', 'released'),
            'unlock': ('held', 'pending'),
            'release_direct': ('pending', 'released'),
            'payment': ('released', 'paid'),
        }[kind]
        d[src], d[dst] = -a, a
    elif kind in ('coupon', 'killer'):
        if a <= 0 or c < 0:
            raise ValueError('El apoyo debe ser positivo y su comisión no negativa.')
        d['gross'], d['commission'], d['pending'] = a, c, money(a-c)
    elif kind in ('commission', 'tax', 'shipping', 'other'):
        if a == 0:
            raise ValueError('El ajuste no puede ser cero.')
        component = {'tax': 'withholding'}.get(kind, kind)
        d[component] = a
        d['pending'] = -a
    elif kind == 'refund':
        if a <= 0 or bucket not in BUCKETS:
            raise ValueError('Seleccione un importe positivo y un origen válido.')
        d['refunded'] = a
        d[bucket] = -a
    else:
        raise ValueError('Tipo de evento desconocido.')
    return d


def apply_event(before, deltas):
    """Apply deltas and validate the financial identity and nonnegative states.

    The 'pending' bucket is allowed to go below zero (e.g. penalty after a
    full refund), but held/released/paid can never fall below zero.
    """
    old = state(before)
    d = state(deltas)
    new = {k: money(old[k] + d[k]) for k in KEYS}
    for key in ('gross', 'withholding', 'commission', 'killer_commission',
                'coupon_commission', 'shipping',
                'other', 'refunded', 'held', 'released', 'paid'):
        if new[key] < 0:
            raise ValueError('El movimiento dejaría negativo el concepto %s; revise los eventos.' % key)
    if net(new) != money(sum(new[k] for k in BUCKETS)):
        raise ValueError('El movimiento descuadra los saldos financieros.')
    return new
