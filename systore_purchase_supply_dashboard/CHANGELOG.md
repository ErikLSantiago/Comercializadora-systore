# Historial de cambios

## 18.0.1.7.0

- La deuda extranjera incorpora un selector visual para consultar saldos y abonos en MXN o USD.
- Los conceptos originalmente expresados en MXN, como importación, se convierten a USD con el tipo de cambio efectivo de la orden y, si aún no existe, con `x_exchange_rate`.
- Demanda se consolida por producto/SKU y conserva almacenes, canales, piezas solicitadas y piezas listas.
- Se muestran por separado el faltante original, las piezas cubiertas por compras confirmadas y las piezas que realmente falta comprar.
- La cobertura toma únicamente cantidades confirmadas pendientes de recepción del mismo producto y respeta los filtros de almacén y canal.
- Cuando la compra se recibe, deja de contarse como mercancía en camino; el inventario recibido pasa a intervenir mediante la disponibilidad del traslado, evitando una doble resta.
- Al seleccionar un SKU se abre el análisis de demanda filtrado por ese producto y mes.

## 18.0.1.6.5

- Se agregó al encabezado el filtro **Tipo de proveedor**: Todos, Nacional e Internacional.
- El filtro se aplica a recepciones, Productos recibidos, rankings de compras, proveedores disponibles y deuda histórica.
- Las métricas de ventas y demanda permanecen independientes del tipo de proveedor.
- Productos recibidos incorpora una fila de **Total general**.
- El total general suma piezas y valores de Solicitadas, Recibidas brutas, Devueltas, Recibidas netas y Pendientes.
- La fila total responde al rango, proveedor, tipo de proveedor, almacén, canal y modo de valuación seleccionados.

## 18.0.1.6.4

- Productos recibidos incorpora un selector de valuación: Costo USD, Costo MXN y Costo neto.
- Cada estado muestra simultáneamente las piezas y su valor: Solicitadas, Recibidas brutas, Devueltas, Recibidas netas y Pendientes.
- Costo USD utiliza la mercancía `x_gross_usd` de compras internacionales.
- Costo MXN convierte esa mercancía con el `x_exchange_rate` de cada orden.
- Costo neto utiliza el costo global MXN tanto para compras internacionales como nacionales.
- En proveedores nacionales, los modos Costo USD y Costo MXN muestran un guion y conservan visibles las piezas.

## 18.0.1.6.3

- El resumen de Productos recibidos incorpora Costo proveedor USD, Costo proveedor MXN y Costo neto MXN.
- El costo proveedor USD utiliza exclusivamente `x_gross_usd`, sin logística ni importación.
- El costo proveedor MXN convierte la mercancía USD con `x_exchange_rate` de cada orden.
- El costo neto MXN utiliza el costo global unitario recosteado, que incorpora mercancía, logística e importación.
- Los costos se aplican a las piezas recibidas netas del rango, descontando devoluciones.
- Para proveedores nacionales se ocultan los costos de mercancía USD/MXN y sólo se muestra el costo neto MXN.

## 18.0.1.6.2

- Se retiró el Top 10 y el desglose visible por producto de **Productos recibidos**.
- El resumen ahora contiene una sola línea con las sumatorias de cada proveedor.
- Se conservan Solicitadas, Recibidas brutas, Devueltas, Recibidas netas y Pendientes.
- Al seleccionar una línea se abre **Recepciones de compra** filtrado por ese proveedor.
- Los proveedores se ordenan de mayor a menor por piezas recibidas brutas, sin limitar el resultado a diez proveedores.

## 18.0.1.6.1

- **Productos recibidos** ahora se organiza por proveedor y después por producto.
- Se agregaron las columnas Solicitadas, Recibidas brutas, Devueltas, Recibidas netas y Pendientes.
- Cada proveedor muestra una fila de totales para las cinco cantidades.
- Recibidas, devueltas y netas respetan el rango Desde/Hasta seleccionado.
- Solicitadas y pendientes utilizan las líneas de compra relacionadas y su recepción neta histórica.
- Los productos continúan abriendo los movimientos de inventario que forman el resultado.

## 18.0.1.6.0

- Se agregó al tablero el Top 10 de **Productos recibidos** basado directamente en movimientos terminados desde proveedor.
- El tablero incorpora fechas Desde/Hasta para consultar recepciones; al cambiar el mes, el rango se ajusta al mes completo.
- Cada producto recibido permite abrir los movimientos de inventario que forman su cantidad.
- Recepciones de compra ahora separa piezas recibidas brutas, devueltas y recibidas netas.
- Los movimientos terminados hacia una ubicación de proveedor se identifican como **Devolución a proveedor**.
- Se muestran la fecha y las transferencias relacionadas con cada devolución.
- Las piezas pendientes y la valuación recibida se calculan sobre la recepción neta.
- Se corrigió la pérdida de contexto al abrir órdenes desde los paneles de deuda (`undefined.action`).

## 18.0.1.5.2

- Se corrigió la prioridad del estado manual que mantenía una orden en Pendiente aunque tuviera abonos.
- El selector manual ahora contiene únicamente **Automático según abonos** y **Pagada**.
- En modo Automático, cualquier abono menor al total clasifica la orden como Parcial.
- La migración convierte los antiguos valores manuales Pendiente y Parcial a Automático.
- Los renglones de deuda muestran tanto el saldo como el importe ya abonado en USD y MXN.

## 18.0.1.5.1

- La deuda se presenta en dos sectores: proveedores nacionales y proveedores extranjeros.
- El origen nacional o extranjero se determina con la clasificación de la orden de compra.
- Se agregó el desplegable **Estado de pago** con Automático, Pendiente, Parcial y Pagada.
- Al marcar una orden como Pagada, sus saldos pendientes efectivos pasan a cero y desaparece de la deuda del tablero.
- La deuda utiliza el histórico completo de órdenes confirmadas o terminadas, independientemente del mes seleccionado.
- El mes continúa aplicándose a demanda, recepciones, piezas y rankings operativos.

## 18.0.1.5.0

- Los abonos internacionales registran monto USD, fecha y tipo de cambio individual.
- El equivalente MXN de cada abono se calcula automáticamente como USD por tipo de cambio.
- El tipo de cambio efectivo se calcula de forma ponderada: total MXN pagado entre total USD pagado.
- La deuda internacional se separa en mercancía USD, logística USD e importación MXN.
- Cada concepto se atribuye a su beneficiario: proveedor de mercancía, proveedor logístico o proveedor de importación.
- El tablero muestra simultáneamente el saldo pendiente en USD y su equivalente en MXN.
- Las compras nacionales toman como obligación el total de la orden con impuestos (`amount_total`).

## 18.0.1.4.6

- Se retiró la lista One2many de abonos incrustada en la orden de compra.
- Se agregó el botón **Abrir abonos**, que abre una acción independiente filtrada por la orden actual.
- La acción entrega directamente los IDs de las vistas list/form correctas y un contexto limpio.
- La orden de compra ya no intenta analizar la vista de productos del recosteo como una vista de pagos.

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
