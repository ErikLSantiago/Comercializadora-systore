import math


"""Presentation grouping and UPC input checks; stock rules remain in Odoo."""


def group_pick_rows(rows):
    groups = {}
    for row in rows:
        key = '%s:%s:%s' % (row['product_id'], row['location_id'], row['uom_id'])
        if key not in groups:
            groups[key] = {**row, 'id': key, 'qty': 0, 'line_ids': [],
                           'picking_ids': [], 'origins': [], 'lots': [], 'require_upc': False}
        group = groups[key]
        group['qty'] += row['qty']
        group['line_ids'].append(row['id'])
        for field, value in [('picking_ids', row['picking_id']), ('origins', row['origin']), ('lots', row['lot'])]:
            if value and value not in group[field]:
                group[field].append(value)
        group['require_upc'] |= row['require_upc']
    for group in groups.values():
        group['origin'] = ', '.join(group['origins'])
        group['lot'] = ', '.join(group['lots'])
    return sorted(groups.values(), key=lambda r: (r['product'], r['location'], r['id']))


def normalize_capture(rows, payload):
    if not isinstance(payload, list) or len(payload) != len(rows):
        raise ValueError('Confirme todos los productos de esta recolección.')
    expected = {r['id']: r for r in rows}
    captured = {}
    for item in payload:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str):
            raise ValueError('Grupo de recolección inválido.')
        row = expected.get(item['id'])
        if not row or row['id'] in captured:
            raise ValueError('El grupo no pertenece a esta recolección o está repetido.')
        barcode = item.get('upc', '')
        if not isinstance(barcode, str) or len(barcode) > 256:
            raise ValueError('UPC inválido.')
        barcode = barcode.strip()
        quantity = item.get('quantity', row['qty'])
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or not math.isfinite(quantity) or quantity < 0 or quantity > row['qty']:
            raise ValueError('Las piezas deben estar entre cero y la cantidad disponible.')
        rounding = row.get('rounding', 0.00001)
        if not math.isclose(quantity, round(quantity / rounding) * rounding, rel_tol=0, abs_tol=1e-8):
            raise ValueError('La cantidad no respeta la unidad de medida del producto.')
        if row['require_upc'] and quantity > 0 and not barcode:
            raise ValueError('Capture el UPC del producto antes de validar.')
        captured[row['id']] = {'upc': barcode, 'quantity': quantity}
    if not any(value['quantity'] > 0 for value in captured.values()):
        raise ValueError('Registre al menos una pieza para validar.')
    return captured


def allocate_pick_quantities(rows, captured, capacities):
    """Allocate group quantities only to their original move lines, in ID order."""
    result = {}
    for row in rows:
        remaining = captured[row['id']]['quantity']
        for line_id in sorted(row['line_ids']):
            capacity = capacities[line_id]
            amount = min(remaining, capacity)
            result[line_id] = amount
            remaining = max(remaining - amount, 0)
        if remaining > 0.00001:
            raise ValueError('La cantidad supera la reserva de esta ubicación.')
    return result
