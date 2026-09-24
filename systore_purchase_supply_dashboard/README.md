# Analítica de compras

Versión preparada para producción en Odoo 18.

## Alcance

- Piezas ordenadas, recibidas y pendientes por línea de compra.
- Cohorte mensual por primera recepción validada.
- Valuación MXN con los campos de `purchase_recosteo_importacion`.
- Demanda histórica desde órdenes de venta con traslados parciales, consolidada por SKU y filtrable por mes o Todos.
- El selector Demanda hasta acumula los meses anteriores hasta el corte seleccionado y excluye cualquier mes posterior.
- El filtro Producto permite buscar y seleccionar uno o varios SKU simultáneamente.
- Piezas solicitadas, listas, faltante original, cobertura en compras confirmadas y necesidad neta por producto.
- El panel operativo simplificado muestra Solicitadas, En compra y Por comprar; las piezas listas dejan de aparecer cuando la operación sale de demanda.
- El histórico representa demanda todavía pendiente: las operaciones Listas, Terminadas o Canceladas dejan de formar parte del panel.
- Canal Mayoreo por prefijo de almacén/ubicación `MXMAY` o `SDMAY`.
- Canal Minorista para cualquier otro almacén.
- Trazabilidad Compra → lote → salida → Venta.
- Traslados parciales proporcionados por `stock_upc_validation`.
- Pagos operativos manuales por concepto, fecha, moneda y tipo de cambio, sin efectos contables.
- Gráfica de Demanda de piezas con cantidades cubiertas y por comprar.
- Gráfica de pastel con piezas solicitadas en espera por canal; el número de órdenes se conserva como dato secundario.
- Gráfica de pastel con piezas de compra recibidas y pendientes.
- Resumen de productos recibidos directamente del historial de movimientos, totalizado por proveedor y con rango Desde/Hasta.
- Sumatorias por proveedor de solicitadas, recibidas brutas, devueltas, recibidas netas y pendientes.
- Cada línea de proveedor abre Recepciones de compra con el proveedor aplicado como filtro.
- Para compras internacionales se muestran mercancía USD, mercancía convertida a MXN con `x_exchange_rate` y costo neto MXN.
- La mercancía internacional excluye expresamente logística e importación; el costo neto MXN sí las incorpora.
- Para compras nacionales sólo se presenta el costo neto MXN.
- El selector de valuación de Productos recibidos cambia entre Costo USD, Costo MXN y Costo neto sin ocultar las piezas.
- Cada estado de recepción muestra su cantidad y el valor calculado con el modo seleccionado.
- El filtro Tipo de proveedor permite consultar únicamente compras Nacionales o Internacionales.
- Productos recibidos incluye un total general de cantidades y valores para los filtros aplicados.
- Recepciones brutas, devoluciones a proveedor y recepciones netas por línea de compra.
- Deuda histórica de mercancía separada entre proveedores nacionales y extranjeros, con selector MXN/USD, expansión de proveedores y reporte completo con deuda original, pagos y saldo por proveedor al corte.
- Control de líneas de crédito de proveedor con límite, moneda, crédito ocupado y disponible.
- Condición Contado/Crédito independiente por orden, aunque el proveedor tenga una línea autorizada.
- Inicio y vencimiento de crédito capturados directamente por orden; los días naturales se calculan entre ambas fechas.
- Gráfica con una barra por proveedor que compara el límite total contra el crédito ocupado.
- En compras internacionales la línea consume únicamente mercancía USD; logística e importación no forman parte del crédito del proveedor.
- Los abonos parciales liberan línea automáticamente y las órdenes pagadas dejan de consumir crédito.
- Ranking de productos y proveedores por piezas confirmadas, recibidas y pendientes.
- Filtro de proveedor para gráficas y listados de compras.
- Acceso controlado mediante un grupo propio configurable desde Analítica de compras > Configuración > Usuarios con acceso.
- Clasificación explícita de almacenes como Mayoreo, Minorista o Sin gestión para compras.
- Los almacenes sin gestión quedan fuera de todos los análisis, filtros y reportes del módulo.
- El encabezado operativo utiliza fondo blanco y muestra Analítica de compras en texto negro.
- Los paneles Demanda y Productos recibidos permiten ocultar o mostrar independientemente su tabla para compactar el tablero.
- Después de los filtros y una separación visual, el tablero presenta Crédito con proveedores; debajo, las deudas extranjera y nacional comparten una misma fila, en ese orden.
- Las tarjetas Piezas solicitadas, En compra y Por comprar se retiraron de la interfaz; sus cálculos continúan alimentando la gráfica de demanda.
- El acceso rápido Mes anterior selecciona el mes calendario previo y sincroniza su rango de recepciones.
- El panel Demanda muestra el Top 10 por piezas solicitadas; el análisis completo permanece disponible desde su botón.
- La deuda extranjera inicia en USD y conserva el cambio manual a MXN.
- Los rankings de productos y proveedores permiten abrir el reporte completo agrupado.
- La gráfica Monto comprado por proveedor distribuye el valor solicitado de la cohorte seleccionada según la valuación elegida.
- La gráfica Monto comprado por proveedor alterna entre Costo USD, Costo MXN y Costo neto; Costo USD es la selección inicial.
- Productos recibidos inicia en Costo USD y conserva sus tres modos de valuación.

## Dependencias

- `purchase_stock`
- `sale_stock`
- `web`
- `purchase_recosteo_importacion`
- `wholesale_allocation`
- `stock_upc_validation`

## Configuración inicial

1. Verificar que los almacenes de Mayoreo usen el código/prefijo `MXMAY` o `SDMAY`.
2. Abrir **Analítica de compras > Tablero**.
3. Seleccionar un mes; el mes actual aparece por defecto.
4. Presionar **Actualizar demanda**.
5. Un administrador puede ajustar los usuarios autorizados y los canales de almacén desde **Analítica de compras > Configuración**.
6. La pestaña superior **Configuración** abre directamente la configuración general de acceso y conserva el submenú de Almacenes y canales.
7. En el contacto del proveedor, abrir **Crédito de proveedor** para informar la autorización, moneda y límite.
8. En cada OC, abrir **Pagos y abastecimiento**, elegir Contado o Crédito y, cuando aplique, capturar Inicio de crédito y Vencimiento crédito.

## Reglas de la primera versión

- Recepciones: sólo suma movimientos terminados desde una ubicación Proveedor hacia una ubicación Interna.
- Una OC sólo entra al reporte si cuenta con al menos una recepción válida; confirmar la compra o informar `qty_received` sin movimiento no la incorpora.
- Productos recibidos: identifica las OC con una recepción válida dentro del rango y suma como Solicitadas todas sus líneas de producto.
- El rango de Productos recibidos se aplica a la primera recepción válida de la OC; las entradas posteriores actualizan esa cohorte sin repetir la orden en otros meses.
- Recibidas brutas: suma exclusivamente las piezas de movimientos terminados Proveedor → Interna.
- Devolución a proveedor: movimiento terminado Interna → Proveedor.
- Recepción neta: piezas recibidas brutas menos piezas devueltas al proveedor.
- Primera recepción: fecha mínima de un movimiento terminado Proveedor → Interna.
- Compra internacional automática: existe costo base o logística capturada en USD.
- La deuda del tablero y el estado efectivo de pago consideran únicamente mercancía del proveedor de la orden; logística e importación quedan fuera de este análisis.
- El tipo de cambio efectivo es ponderado por los abonos de mercancía: MXN pagados al proveedor / USD pagados al proveedor.
- Si todavía no existen abonos USD, el equivalente pendiente usa `x_exchange_rate` de la orden.
- Compra nacional: el monto por pagar es `amount_total`, incluido el impuesto de la orden.
- El desplegable **Estado efectivo de pago** permite conservar el cálculo automático o fijar manualmente Pendiente, Parcial o Pagada.
- En modo Automático: sin abonos es Pendiente, con abonos incompletos es Parcial y con el total cubierto es Pagada.
- Una orden marcada manualmente como Pagada no aporta saldo pendiente a la trazabilidad ni al tablero.
- La captura visible de abonos se limita temporalmente a Mercancía; los registros históricos de Logística e Importación se conservan ocultos.
- Los abonos de Mercancía pueden eliminarse para corregir errores operativos; el saldo y el estado se recalculan al eliminar.
- Los días de crédito son naturales y se calculan como la diferencia entre Inicio de crédito y Vencimiento crédito, sin mover fines de semana o festivos.
- La línea autorizada del proveedor no determina la condición de la compra; cada OC debe definirse expresamente como Contado o Crédito.
- Una compra de Contado continúa en la deuda operativa si está pendiente, pero no consume la línea de crédito.
- Las órdenes confirmadas a crédito consumen la línea por su saldo pendiente de mercancía, aunque la fecha de inicio todavía no haya llegado.
- La deuda se calcula al cierre del Mes operativo: incluye órdenes confirmadas hasta ese día y resta únicamente los abonos cuya fecha no sea posterior al corte.
- El reporte internacional expresa deuda, pagos y saldo en USD y MXN; el nacional presenta los mismos importes en MXN.
- Las órdenes marcadas manualmente como Pagada permanecen fuera de la deuda en cualquier corte histórico.
- Costo internacional: `x_calc_price_mxn`.
- Costo nacional: `price_unit`, convertido a moneda de compañía cuando corresponda.
- Cada actualización procesa solamente un mes. No existe actualización global.
- Demanda: operaciones `Parcial` cuya ubicación origen se llama `Existencias`.
- Periodo de demanda: mes de `scheduled_date` de la operación.
- Demanda hasta: al seleccionar un mes se usa la fotografía más reciente de cada operación/producto disponible hasta ese mes; Todos conserva el universo vigente completo.
- En existencia: suma de Piezas listas (`reserved_qty`) de las operaciones incluidas en el corte.
- Faltante original por producto: `max(piezas solicitadas - piezas listas, 0)`.
- Cobertura en compra: piezas de órdenes confirmadas del mismo producto que aún no han sido recibidas, respetando almacén y canal cuando se filtran.
- Por comprar: `max(faltante original - cobertura en compra, 0)`.
- En la vista histórica, la cobertura disponible se asigna primero al mes de demanda más antiguo para no reutilizar una misma compra en varios meses.
- Demanda de piezas: Cubiertas = Solicitadas - Por comprar.
- El bloque de gráficas inicia separado visualmente del área de filtros para facilitar la lectura del tablero.
- Las piezas ya recibidas dejan de contarse como cobertura en camino para evitar descontarlas también cuando pasan a piezas listas en inventario.
- La gráfica de órdenes en espera se segmenta por cantidad de piezas solicitadas; cada orden de venta se cuenta una sola vez únicamente en el dato secundario.
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
13. Retirar un usuario desde Configuración y comprobar que desaparezca el menú Analítica de compras para ese usuario.
14. Marcar un almacén como Sin gestión para compras y comprobar que desaparezca de Demanda, recepciones y deuda.
15. Cambiar un almacén entre Mayoreo y Minorista y comprobar que sus líneas históricas cambien de canal.
16. Configurar un proveedor con límite USD 1,000, confirmar dos órdenes a crédito y comprobar que el utilizado y disponible se acumulen.
17. Confirmar una compra de Contado para el mismo proveedor y comprobar que no consuma crédito.
18. Registrar un abono parcial USD y comprobar que libere la misma cantidad de línea.
19. Capturar distintos inicios y vencimientos por orden y verificar el cálculo de días naturales.
20. Marcar una orden como Pagada y comprobar que deje de consumir crédito.
21. Cubrir toda la mercancía de una compra internacional y comprobar que quede Pagada aunque Logística o Importación conserven saldo histórico.

## Limitaciones deliberadas de V1

- El tablero usa fotografías mensuales regenerables; se actualiza mediante el botón del tablero.
- Wholesale Allocation relaciona órdenes completas, no cantidades por línea.
- Las ventas se concilian históricamente mediante lote; no se fuerza una asociación manual.
- Los pagos manuales no crean facturas, pagos ni asientos contables.
