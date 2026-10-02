# Tablero de operaciones · Odoo 18

Versión **18.0.1.1.0** · Nombre técnico `systore_operations_dashboard`.

## Cambios

- Recepciones se divide en **Ingresos (In)** y **Almacenamiento (Storage)**. Solo aparecen los tipos nativos activos y seleccionados: una recepción de un paso muestra In; dos pasos muestran In y Storage.
- Pick, Pack y Out muestran piezas solicitadas en su unidad de inventario, batches y órdenes de venta. El detalle agrupa las operaciones de cada batch y muestra también sus lotes nativos cuando existen.
- Pick y Pack abren pantallas sencillas que reutilizan el asistente de `stock_upc_validation` y guardan las series con `adicional_serial_number`.
- Out comienza con una lista vacía para escanear paquetes y valida cada salida al completar sus paquetes, conservando los asistentes y controles nativos de Odoo.
- Se conserva la aplicación independiente Operaciones, la selección de almacén, permisos por usuario, checks de tipos, referencia del proveedor y filtros de fecha. También la corrección del registro de la acción del tablero que originaba el error KeyNotFoundError.

## Instalación y configuración

Actualice el addon existente; no instale una copia con otro nombre. Requiere Odoo 18 y los módulos `stock_picking_batch`, `adicional_serial_number` y `stock_upc_validation`, además de sus dependencias. Use las versiones de UPC y series suministradas para esta integración. Este ZIP contiene únicamente el tablero actualizado.

1. Copie `systore_operations_dashboard` al directorio de addons de su rama de pruebas de Odoo.sh. Actualice la lista de aplicaciones y actualice este módulo. La actualización carga Python, vistas y assets; después recargue el navegador.
2. En cada almacén, marque **Participa en tablero de operaciones**, asigne **Usuarios del tablero** y seleccione **Tipos de operación incluidos**. Solo un administrador de Inventario puede cambiar estas opciones. Si activa nuevas etapas o crea tipos después, márquelos aquí.
3. En los ajustes de Stock UPC Validation, incluya los almacenes que usarán las pantallas guiadas. En Pick active la exigencia de UPC; en Pack active **Exigir guía en empaque**. Registre los UPC principales o múltiples de los productos.
4. Con entrega de **dos pasos**, active **Exigir guía en empaque en el tipo Pick**: esta etapa captura UPC, NS/IMEI y guía por orden antes de pasar a Out. Como no existe un Pack independiente, un batch abre su lista de órdenes y cada orden se prepara individualmente.

No se cambian rutas, ubicaciones ni número de pasos del almacén. En tres pasos, las validaciones avanzan los movimientos nativos Existencias → Zona de empaquetado → Salida → Clientes. Los nombres de ubicaciones pueden variar. En un paso, Out conserva los requisitos nativos de la entrega y requiere un paquete o guía para identificarla.

## Operar Pick

Use **Batches** para consultar o crear batches nativos del tipo correspondiente. También puede usar la acción nativa Añadir a lote. La pantalla guiada requiere que Pick pertenezca a un batch; no agrupa pedidos arbitrariamente.

Al abrir un batch de Pick, se suman las piezas por producto entre sus órdenes. La pantalla muestra números de orden, producto, piezas solicitadas, recolectadas y UPC. Registre la cantidad recolectada y escanee el UPC de cada producto; **Validar y continuar** comprueba el código y avanza mediante la validación original de UPC/Odoo. Un UPC corresponde al total recolectado del producto, igual que en el módulo suministrado. Cantidades parciales conservan el asistente de pedido pendiente.

La operación debe estar completamente disponible. Se rechazan cantidades negativas, cantidades superiores a las disponibles y excepciones de omisión de UPC en esta pantalla. Las excepciones autorizadas siguen disponibles mediante el flujo original del módulo.

## Operar Pack

Cada orden conserva su propia guía. Si abre un batch de Pack, aparece la lista de sus operaciones con el botón **Operar**.

La pantalla solicita UPC y NS/IMEI por pieza y número de guía de la orden. El botón de validación ejecuta las comprobaciones originales, registra las series en `stock.move.line.serial`, aplica cantidades y avanza la operación. La guía se propaga a Out mediante el módulo UPC suministrado. Los códigos se comprueban al pulsar Validar; el contador de capturas no sustituye esa comprobación.

El registro de NS/IMEI adicionales conserva la lógica del módulo adjunto. Los lotes y series nativos de Odoo mantienen sus propios controles y reservas; no son el mismo concepto que un batch.

## Escanear Out

Abra Salidas para comenzar una sesión vacía del filtro seleccionado, o abra una operación/batch concreto. Escanee un código y presione Enter:

- Si existen paquetes nativos, use sus códigos. Una salida con varios paquetes se valida únicamente después de escanearlos todos; una guía que cubra varios paquetes no los sustituye.
- Si no existen paquetes nativos, la guía identifica **un paquete por operación de salida**. Para contar varios bultos de una orden, cree los paquetes nativos durante el empaque.
- Se rechazan códigos desconocidos, guías ambiguas, duplicados, operaciones fuera de la sesión y salidas sin disponibilidad. Una salida que mezcla piezas empaquetadas y sueltas exige completar el empaque.
- Cada escaneo actualiza paquetes escaneados y entregas validadas. Si Odoo solicita UPC, lotes, series, guía o un asistente adicional, se muestra ese flujo; no se omite. **Validar completas** permite retomar las operaciones ya escaneadas después de resolver un asistente.

La sesión corresponde al operador que la creó y conserva sus escaneos mientras exista el registro transitorio. Al iniciar otra sesión, la lista comienza vacía. Las salidas ya hechas no se pueden entregar nuevamente. El escaneo de un batch abre todas sus operaciones pendientes autorizadas.

## Contadores y fechas

En In y Storage se usa la **Fecha esperada de la compra (`date_planned`)**, la referencia del proveedor (`partner_ref`) y los bultos informativos de la OC. Bultos y piezas se cuentan una sola vez por compra dentro de cada etapa. Piezas representa el total solicitado de productos físicos, no un saldo que disminuya con cada recepción parcial. En recepciones sin compra, se usa la demanda de la operación.

En expediciones y transferencias se usan fecha programada y demanda de movimientos pendientes. Los totales de diferentes etapas no se suman: una misma mercancía puede estar en varias etapas del flujo. Transferencias muestra movimientos desde Existencias del almacén hacia cualquier ubicación, sujeto a los tipos seleccionados; puede coincidir con Pick.

Hoy y Mañana respetan la zona horaria del usuario. Atrasadas usa el día actual; Todas incluye pendientes sin fecha. Se excluyen registros hechos y cancelados. El detalle muestra hasta 60 filas, pero los contadores y la lista completa incluyen todas las operaciones accesibles.

Un batch puede abarcar fechas distintas. Su fila resume las operaciones del filtro; al operarlo se abre el batch completo, para mantener la agrupación nativa. Se comprueba que todas sus operaciones pendientes pertenezcan al almacén y etapa autorizados.

## Seguridad

Los permisos de almacén se verifican en el servidor en cada consulta y operación. Se mantienen reglas de compañía y permisos nativos. El resumen permite al operador de Inventario leer únicamente datos operativos de las compras y los números de venta vinculados, sin dar acceso a precios ni edición de Compras/Ventas.

Consultar el tablero no valida operaciones ni cambia reservas. Abrir una preparación solicita disponibilidad; pulsar Validar o escanear una salida completa sí opera los movimientos. No se cambian los módulos UPC y series suministrados ni sus reglas de validación.

## Verificación

Comprobaciones locales: 19 pruebas Python de fechas, agregaciones, etapas y resolución de paquetes; compilación de ambas plantillas con Owl de Odoo 18; filtros y navegación del tablero; sesión de escaneo vacía, asistente nativo y errores del cliente; registro de ambas acciones con el conversor y cargador nativos; sintaxis Python/JavaScript, XML y referencias de archivos.

Estas comprobaciones usan adaptadores de ORM y ejecución de plantillas sin montar un navegador. **No se ejecutó una instancia completa de Odoo ni se validaron movimientos reales en Odoo.sh.**

Se incluyen pruebas `TransactionCase` en `tests/test_operations_dashboard.py`, incluyendo el recorrido nativo de tres pasos con UPC incorrecto, UPC correcto, series, guía y entrega escaneada. Ejecútelas en su base de pruebas con `--test-enable --test-tags /systore_operations_dashboard --stop-after-init`.

Antes de producción, pruebe su configuración real de uno, dos y tres pasos, dos órdenes en un batch del mismo producto, recepción parcial, lotes/series nativos, varios paquetes, códigos duplicados y usuarios restringidos. Compruebe los asistentes de pedido pendiente y que la guía llegue a Out.
