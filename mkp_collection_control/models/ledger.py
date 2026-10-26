"""Pure deterministic MXN-compatible ledger; no Odoo imports.

Each financial event is an immutable signed DELTA, not a replacement snapshot.
'paid' is a payment *reported by the marketplace*, NOT a confirmed bank deposit.
The outstanding/pending bucket can be negative for subsequent marketplace fees.
"""
from decimal import Decimal, ROUND_HALF_UP

KEYS = ('gross', 'withholding', 'commission', 'shipping', 'other',
        'refunded', 'pending', 'held', 'released', 'paid')
BUCKETS = ('pending', 'held', 'released', 'paid')
CENTS = Decimal('0.01')


def money(value):
    return Decimal(str(value or 0)).quantize(CENTS, rounding=ROUND_HALF_UP)


def state(values=None):
    values = values or {}
    return {key: money(values.get(key, 0)) for key in KEYS}


def net(values):
    return money(values['gross'] - values['withholding']
                 - values['commission'] - values['shipping']
                 - values['other'] - values['refunded'])


def event_deltas(kind, *, amount=0, extra_commission=0,
                 gross=0, withholding=0, commission=0,
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
                    commission=money(commission), shipping=money(shipping),
                    other=money(other))
        if any(v < 0 for v in vals.values()):
            raise ValueError('El desglose inicial no admite valores negativos.')
        d.update(vals)
        d['pending'] = money(vals['gross'] - vals['withholding']
                             - vals['commission'] - vals['shipping'] - vals['other'])
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
    for key in ('gross', 'withholding', 'commission', 'shipping',
                'other', 'refunded', 'held', 'released', 'paid'):
        if new[key] < 0:
            raise ValueError('El movimiento dejaría negativo el concepto %s; revise los eventos.' % key)
    if net(new) != money(sum(new[k] for k in BUCKETS)):
        raise ValueError('El movimiento descuadra los saldos financieros.')
    return new
