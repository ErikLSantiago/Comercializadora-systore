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
        if row['require_upc'] and not barcode:
            raise ValueError('Capture el UPC del producto antes de validar.')
        captured[row['id']] = {'upc': barcode}
    return captured
