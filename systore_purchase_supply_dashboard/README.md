# Systore - Tablero de Compras y Abastecimiento

Versión de pruebas para Odoo 18.

## Alcance

- Piezas ordenadas, recibidas y pendientes por línea de compra.
- Cohorte mensual por primera recepción validada.
- Valuación MXN con los campos de `purchase_recosteo_importacion`.
- Demanda desde órdenes de venta con traslados parciales.
- Piezas solicitadas, listas y faltantes por operación y SKU.
- Canal Mayoreo por prefijo de almacén/ubicación `MXMAY` o `SDMAY`.
- Canal Minorista para cualquier otro almacén.
- Trazabilidad Compra → lote → salida → Venta.
- Traslados parciales proporcionados por `stock_upc_validation`.
- Pagos operativos manuales, sin efectos contables.

## Dependencias

- `purchase_stock`
- `sale_stock`
- `web`
- `purchase_recosteo_importacion`
- `wholesale_allocation`
- `stock_upc_validation`

## Configuración inicial

1. Verificar que los almacenes de Mayoreo usen el código/prefijo `MXMAY` o `SDMAY`.
2. Abrir **Abastecimiento > Tablero**.
3. Seleccionar un mes; el mes actual aparece por defecto.
4. Presionar **Actualizar demanda**.

## Reglas de la primera versión

- Recepciones: usa `purchase.order.line.qty_received`.
- Primera recepción: fecha mínima de un movimiento terminado desde una ubicación de proveedor.
- Si una compra aún no tiene recepción, la fecha de reporte provisional es la fecha de la OC.
- Compra internacional automática: existe costo base o logística capturada en USD.
- Costo internacional: `x_calc_price_mxn`.
- Costo nacional: `price_unit`, convertido a moneda de compañía cuando corresponda.
- Cada actualización procesa solamente un mes. No existe actualización global.
- Demanda: operaciones `Parcial` cuya ubicación origen se llama `Existencias`.
- Periodo de demanda: mes de `scheduled_date` de la operación.
- Faltante por producto: `max(piezas solicitadas - piezas listas, 0)`.
- Trazabilidad: el nombre del lote debe coincidir exactamente con el número de la OC.

## Pruebas recomendadas

1. OC de 100 piezas con recepción parcial de 98.
2. Segunda recepción de 2 piezas en otro mes: la primera fecha debe conservarse.
3. Compra nacional en MXN.
4. Compra internacional con mercancía y logística USD e importación MXN.
5. Venta Minorista surtida con un lote cuyo nombre sea la OC.
6. Venta Mayoreo con una o varias OC de Wholesale Allocation.
7. Venta con traslado Parcial desde Existencias.
8. Compra con monto a pagar y varios abonos manuales.

## Limitaciones deliberadas de V1

- El tablero usa fotografías mensuales regenerables; se actualiza mediante el botón del tablero.
- Wholesale Allocation relaciona órdenes completas, no cantidades por línea.
- Las ventas se concilian históricamente mediante lote; no se fuerza una asociación manual.
- Los pagos manuales no crean facturas, pagos ni asientos contables.
