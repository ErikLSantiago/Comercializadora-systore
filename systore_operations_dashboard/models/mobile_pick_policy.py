"""Input validation for the mobile adapter; no stock or UPC rules live here."""
import math


def serial_count(quantity):
    if not math.isfinite(quantity) or quantity <= 0 or not math.isclose(quantity, round(quantity), rel_tol=0, abs_tol=0.00001):
        raise ValueError('La captura móvil de series requiere cantidades enteras positivas.')
    return int(round(quantity))


def normalize_capture(rows, payload):
    if not isinstance(payload, list) or len(payload) != len(rows):
        raise ValueError('Complete las series de todos los productos.')
    expected = {r['id']: r for r in rows}
    captured, used = {}, set()
    for item in payload:
        if not isinstance(item, dict) or type(item.get('id')) is not int:
            raise ValueError('Línea de recolección inválida.')
        row = expected.get(item['id'])
        if not row or row['id'] in captured:
            raise ValueError('La línea no pertenece a esta recolección o está repetida.')
        serials = item.get('serials')
        if not isinstance(serials, list) or len(serials) != serial_count(row['qty']):
            raise ValueError('Capture una serie por cada unidad que debe recoger.')
        clean = []
        for value in serials:
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError('Capture un número de serie válido por pieza.')
            value = value.strip()
            key = (row['picking_id'], value)
            if key in used:
                raise ValueError('Un número de serie está repetido en la misma operación.')
            used.add(key)
            clean.append(value)
        existing = set(row['existing_serials'])
        if not existing.issubset(set(clean)):
            raise ValueError('Conserve las series ya registradas; corríjalas desde el formulario original.')
        if row['tracking'] == 'serial' and (len(clean) != 1 or clean[0] != row['lot']):
            raise ValueError('La serie escaneada no coincide con la serie nativa reservada.')
        barcode = item.get('upc', '')
        if not isinstance(barcode, str) or len(barcode) > 256:
            raise ValueError('UPC inválido.')
        captured[row['id']] = {'serials': clean, 'upc': barcode.strip()}
    return captured
