# Systore - Tablero de Compras y Abastecimiento

Primera versión de pruebas para Odoo 18.

## Alcance

- Piezas ordenadas, recibidas y pendientes por línea de compra.
- Cohorte mensual por primera recepción validada.
- Valuación MXN con los campos de `purchase_recosteo_importacion`.
- Demanda abierta por almacén y SKU.
- Existencia física, compras pendientes y faltante por comprar.
- Canal Mayoreo desde `warehouse.is_wholesale`.
- Canal Marketplace configurable en el almacén.
- Trazabilidad Compra → lote → salida → Venta.
- Conteo opcional de traslados completos/parciales cuando está instalado `stock_upc_validation`.
- Pagos operativos manuales, sin efectos contables.

## Dependencias

- `purchase_stock`
- `sale_stock`
- `web`
- `purchase_recosteo_importacion`
- `wholesale_allocation`

`stock_upc_validation` es una integración opcional. Si está instalado, el tablero lee
`systore_batch_readiness_state`; si no está instalado, el tablero sigue funcionando.

## Configuración inicial

1. Abrir Inventario > Configuración > Almacenes.
2. En los almacenes Marketplace seleccionar **Marketplace** como canal de abastecimiento.
3. Los almacenes con **Wholesale** activo se clasifican automáticamente como Mayoreo.
4. Abrir **Abastecimiento > Tablero**.
5. Presionar **Actualizar información**.

## Reglas de la primera versión

- Recepciones: usa `purchase.order.line.qty_received`.
- Primera recepción: fecha mínima de un movimiento terminado desde una ubicación de proveedor.
- Si una compra aún no tiene recepción, la fecha de reporte provisional es la fecha de la OC.
- Compra internacional automática: existe costo base o logística capturada en USD.
- Costo internacional: `x_calc_price_mxn`.
- Costo nacional: `price_unit`, convertido a moneda de compañía cuando corresponda.
- Demanda: cantidad confirmada pendiente de entregar.
- Faltante: `max(demanda - existencia física - compra pendiente de recibir, 0)`.
- Trazabilidad: el nombre del lote debe coincidir exactamente con el número de la OC.

## Pruebas recomendadas

1. OC de 100 piezas con recepción parcial de 98.
2. Segunda recepción de 2 piezas en otro mes: la primera fecha debe conservarse.
3. Compra nacional en MXN.
4. Compra internacional con mercancía y logística USD e importación MXN.
5. Venta Marketplace surtida con un lote cuyo nombre sea la OC.
6. Venta Mayoreo con una o varias OC de Wholesale Allocation.
7. Venta abierta sin inventario ni compra pendiente.
8. Compra con monto a pagar y varios abonos manuales.

## Limitaciones deliberadas de V1

- El tablero usa fotografías regenerables; se actualiza mediante el botón del tablero.
- Wholesale Allocation relaciona órdenes completas, no cantidades por línea.
- Marketplace se concilia históricamente mediante lote; no se fuerza una asociación manual.
- Los pagos manuales no crean facturas, pagos ni asientos contables.
