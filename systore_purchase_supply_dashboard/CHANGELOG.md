# Historial de cambios

## 18.0.1.3.0

- Se agregó una gráfica de barras con el total de órdenes de venta Listas y Parciales.
- Se agregó una gráfica de pastel con la distribución de órdenes entre Mayoreo y Minorista.
- Se agregó una gráfica de pastel con las piezas de compra Recibidas y Pendientes.
- Los conteos de órdenes evitan duplicados cuando una venta tiene más de una operación.
- Si una orden tiene operaciones listas y parciales, se clasifica como Parcial.
- Las gráficas respetan el mes y el almacén seleccionados; las piezas también respetan el filtro de canal.
- Se incluyeron estados visuales sin datos y diseño adaptable para pantallas medianas.

## 18.0.1.2.0

- Canal automático Mayoreo para almacenes/ubicaciones con prefijo `MXMAY` o `SDMAY`.
- Los demás almacenes se clasifican automáticamente como Minorista.
- Se eliminó la clasificación operativa Marketplace/Otro del tablero.
- El tablero principal se simplificó al reporte **Demanda**.
- Demanda se obtiene directamente de operaciones con estado **Parcial**.
- Solo se consideran operaciones cuya ubicación origen se llama **Existencias**.
- El mes se aplica sobre la fecha programada de la operación.
- Se muestran únicamente los productos con piezas faltantes dentro de esas operaciones.
- Los snapshots de versiones anteriores se limpian durante la actualización; no se modifican compras, ventas, inventario ni pagos.

## 18.0.1.1.0

- La actualización exige un único mes y usa el mes actual de forma predeterminada.
- Se eliminaron las actualizaciones globales desde el tablero.
- Compras y recepciones se consultan únicamente para las OC o movimientos afectados por el mes.
- Una recepción posterior actualiza la OC conservando su primera fecha de recepción.
- Demanda y compras por recibir se calculan para documentos originados en el mes seleccionado.
- La trazabilidad por lote se reconstruye únicamente para las salidas del mes.
- Las fotografías mensuales previamente generadas se conservan.

## 18.0.1.0.0

- Primera versión del tablero de compras, abastecimiento, demanda, trazabilidad y pagos manuales.
