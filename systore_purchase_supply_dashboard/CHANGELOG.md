# Historial de cambios

## 18.0.1.4.5

- Se identificó que `list_view_ref` del desglose de recosteo estaba llegando al campo de abonos.
- Los abonos ahora usan vistas list/form propias mediante referencias explícitas.
- La acción de Pagos manuales también queda vinculada explícitamente a su vista correcta.
- Se retiraron los campos temporales de producto, cantidad y precio del modelo de pagos.
- Se retiró la limpieza de vistas; ya no es necesaria al quedar aislada la resolución de vistas.

## 18.0.1.4.4

- La limpieza de vistas residuales ahora se ejecuta tanto al instalar como al actualizar el módulo.
- Se añadió `price_unit` como compatibilidad temporal para desbloquear bases que todavía conservan la vista antigua.
- Producto, cantidad y precio se retiran de la vista residual durante la carga de datos del módulo.
- Estos campos de compatibilidad no intervienen en el cálculo del importe pagado ni de la deuda.

## 18.0.1.4.3

- Se agregó una migración para detectar y reparar vistas residuales de pagos.
- La migración retira de esas vistas todos los campos que no existen en `systore.purchase.payment`, en lugar de agregar campos incompatibles uno por uno.
- La limpieza se limita a vistas del modelo de pagos y a secciones de `systore_payment_line_ids` dentro de órdenes de compra.
- Si una vista inválida no puede repararse, se desactiva para permitir que Odoo utilice la vista vigente del módulo.

## 18.0.1.4.2

- Se restauró `product_qty` como campo opcional de compatibilidad en los pagos manuales.
- Se corrigió el segundo error Owl provocado por una vista residual que esperaba producto y cantidad.
- La cantidad informativa no interviene en el cálculo del importe pagado ni del saldo pendiente.

## 18.0.1.4.1

- Se restauró `product_id` como campo opcional de compatibilidad en los pagos manuales.
- Se corrigió el error Owl al abrir órdenes de compra cuando existe una vista heredada de pagos que todavía referencia ese campo.
- La deuda y el estado de pago continúan calculándose sobre el total de la orden, sin modificar los pagos existentes.

## 18.0.1.4.0

- La gráfica Listas/Parciales ahora utiliza una sola barra horizontal apilada.
- Las gráficas de estados y canales muestran tanto órdenes como piezas relacionadas.
- Los resultados de las gráficas permiten abrir las órdenes o líneas de compra correspondientes.
- Se agregó un filtro de proveedor para la información de compras.
- Se agregó un gráfico-listado de saldos pendientes por proveedor.
- Se agregó un ranking de los diez productos más comprados.
- Se agregó un ranking de los diez proveedores con mayor volumen confirmado.
- Ambos rankings muestran piezas recibidas frente a piezas solicitadas.

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
