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
- Pagos operativos manuales por concepto, fecha, moneda y tipo de cambio, sin efectos contables.
- Gráfica de barras con órdenes de venta listas y parciales.
- Gráfica de pastel con órdenes de venta por canal Mayoreo y Minorista.
- Gráfica de pastel con piezas de compra recibidas y pendientes.
- Resumen de productos recibidos directamente del historial de movimientos, totalizado por proveedor y con rango Desde/Hasta.
- Sumatorias por proveedor de solicitadas, recibidas brutas, devueltas, recibidas netas y pendientes.
- Cada línea de proveedor abre Recepciones de compra con el proveedor aplicado como filtro.
- Para compras internacionales se muestran mercancía USD, mercancía convertida a MXN con `x_exchange_rate` y costo neto MXN.
- La mercancía internacional excluye expresamente logística e importación; el costo neto MXN sí las incorpora.
- Para compras nacionales sólo se presenta el costo neto MXN.
- Recepciones brutas, devoluciones a proveedor y recepciones netas por línea de compra.
- Deuda histórica separada entre proveedores nacionales y extranjeros, mostrada en USD y MXN, con acceso a las órdenes relacionadas.
- Ranking de productos y proveedores por piezas confirmadas, recibidas y pendientes.
- Filtro de proveedor para gráficas y listados de compras.

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

- Recepciones: suma los movimientos terminados desde proveedor vinculados a cada línea de compra.
- Productos recibidos: movimientos terminados cuyo origen es una ubicación de tipo Proveedor dentro del rango seleccionado.
- Devolución a proveedor: movimiento terminado cuyo destino es una ubicación de tipo Proveedor.
- Recepción neta: piezas recibidas brutas menos piezas devueltas al proveedor.
- Primera recepción: fecha mínima de un movimiento terminado desde una ubicación de proveedor.
- Si una compra aún no tiene recepción, la fecha de reporte provisional es la fecha de la OC.
- Compra internacional automática: existe costo base o logística capturada en USD.
- Obligación internacional: mercancía y logística en USD; importación en MXN, cada una conciliada por separado.
- El tipo de cambio efectivo es ponderado por los importes pagados: MXN pagados / USD pagados.
- Si todavía no existen abonos USD, el equivalente pendiente usa `x_exchange_rate` de la orden.
- Compra nacional: el monto por pagar es `amount_total`, incluido el impuesto de la orden.
- El desplegable **Estado de pago** permite conservar el cálculo automático o marcar manualmente la orden como Pagada.
- En modo Automático: sin abonos es Pendiente, con abonos incompletos es Parcial y con el total cubierto es Pagada.
- Una orden marcada manualmente como Pagada no aporta saldo pendiente a la trazabilidad ni al tablero.
- La deuda consulta todas las órdenes confirmadas o terminadas; no se limita al mes seleccionado.
- Costo internacional: `x_calc_price_mxn`.
- Costo nacional: `price_unit`, convertido a moneda de compañía cuando corresponda.
- Cada actualización procesa solamente un mes. No existe actualización global.
- Demanda: operaciones `Parcial` cuya ubicación origen se llama `Existencias`.
- Periodo de demanda: mes de `scheduled_date` de la operación.
- Faltante por producto: `max(piezas solicitadas - piezas listas, 0)`.
- Las gráficas de órdenes cuentan cada orden de venta una sola vez; si tiene una operación parcial, prevalece el estado Parcial.
- La gráfica por canal conserva ambos segmentos para mostrar la composición completa, aun cuando el filtro de canal esté seleccionado.
- La gráfica de piezas usa las líneas de compra de la cohorte mensual y respeta los filtros de almacén y canal.
- El filtro de proveedor se aplica a compras, recepciones, deuda y rankings; no se atribuye proveedor a ventas sin una relación trazable.
- Los segmentos y renglones del tablero son navegables hacia las órdenes o líneas que originan cada resultado.
- Trazabilidad: el nombre del lote debe coincidir exactamente con el número de la OC.

## Pruebas recomendadas

1. OC de 100 piezas con recepción parcial de 98.
2. Segunda recepción de 2 piezas en otro mes: la primera fecha debe conservarse.
3. Compra nacional en MXN.
4. Compra internacional con mercancía y logística USD e importación MXN.
5. Venta Minorista surtida con un lote cuyo nombre sea la OC.
6. Venta Mayoreo con una o varias OC de Wholesale Allocation.
7. Venta con traslado Parcial desde Existencias.
8. Compra internacional de USD 90 con abonos de USD 50 a 17.89, USD 30 a 17.45 y USD 10 a 18.01.
9. Compra nacional y abonos parciales contra el total con impuestos.
10. Marcar una orden antigua como Pagada y comprobar que desaparezca de la deuda histórica.
11. Recibir 10 piezas, devolver 2 a proveedor y comprobar 10 brutas, 2 devueltas, 8 netas y 2 pendientes.
12. Abrir una deuda desde el tablero y comprobar que muestre sus órdenes de compra.

## Limitaciones deliberadas de V1

- El tablero usa fotografías mensuales regenerables; se actualiza mediante el botón del tablero.
- Wholesale Allocation relaciona órdenes completas, no cantidades por línea.
- Las ventas se concilian históricamente mediante lote; no se fuerza una asociación manual.
- Los pagos manuales no crean facturas, pagos ni asientos contables.
