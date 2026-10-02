import math


def receipt_captures(rows, payload):
    if not isinstance(payload, list) or len(payload) != len(rows):
        raise ValueError('Complete todos los productos de la recepción.')
    expected = {row['id']: row for row in rows}
    result = {}
    for item in payload:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str):
            raise ValueError('Producto de recepción inválido.')
        row = expected.get(item['id'])
        if not row or row['product_id'] in result:
            raise ValueError('El producto no pertenece a esta recepción o está repetido.')
        quantity = item.get('quantity')
        if type(quantity) not in (float, int) or not math.isfinite(quantity) or quantity < 0 or quantity > row['qty']:
            raise ValueError('La cantidad a ingresar debe estar entre cero y la cantidad solicitada.')
        barcode = item.get('upc', '')
        if not isinstance(barcode, str) or len(barcode) > 256:
            raise ValueError('UPC inválido.')
        if row['require_upc'] and quantity > 0 and not barcode.strip():
            raise ValueError('Capture los UPC requeridos.')
        result[row['product_id']] = {'quantity': quantity, 'upc': barcode.strip()}
    if not any(value['quantity'] > 0 for value in result.values()):
        raise ValueError('Registre al menos una pieza a ingresar.')
    return result
