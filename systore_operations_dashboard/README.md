# Tablero de operaciones · Odoo 18

Versión **18.0.1.2.0** · Nombre técnico `systore_operations_dashboard`.

## Cambios

- Recepciones se divide en **Ingresos (In)** y **Almacenamiento (Storage)**. Solo aparecen los tipos nativos activos y seleccionados: una recepción de un paso muestra In; dos pasos muestran In y Storage.
- Pick, Pack y Out muestran piezas solicitadas en su unidad de inventario, batches y órdenes de venta. El detalle agrupa las operaciones de cada batch y muestra también sus lotes nativos cuando existen.
- **Pick estrena un panel y un detalle móvil**, con captura de series antes de validar. Pack conserva su pantalla de preparación. Ambos se integran con los módulos UPC y series instalados.
- Out comienza con una lista vacía para escanear paquetes y valida cada salida al completar sus paquetes, conservando los asistentes y controles nativos de Odoo.
- Se conserva la aplicación independiente Operaciones, la selección de almacén, permisos por usuario, checks de tipos, referencia del proveedor y filtros de fecha. También la corrección del registro de la acción del tablero que originaba el error KeyNotFoundError.

## Instalación y configuración

Actualice el addon existente; no instale una copia con otro nombre. Requiere Odoo 18 y los módulos `stock_picking_batch`, `adicional_serial_number` y `stock_upc_validation`, además de sus dependencias. Use las versiones de UPC y series suministradas para esta integración. Este ZIP contiene únicamente el tablero actualizado.

1. Copie `systore_operations_dashboard` al directorio de addons de su rama de pruebas de Odoo.sh. Actualice la lista de aplicaciones y actualice este módulo. La actualización carga Python, vistas y assets; después recargue el navegador.
2. En cada almacén, marque **Participa en tablero de operaciones**, asigne **Usuarios del tablero** y seleccione **Tipos de operación incluidos**. Solo un administrador de Inventario puede cambiar estas opciones. Si activa nuevas etapas o crea tipos después, márquelos aquí.
3. En los ajustes de Stock UPC Validation, incluya los almacenes que usarán las pantallas guiadas. En Pick active la exigencia de UPC; en Pack active **Exigir guía en empaque**. Registre los UPC principales o múltiples de los productos.
4. Con entrega de **dos pasos**, active **Exigir guía en empaque en el tipo Pick**: esta etapa captura UPC, NS/IMEI y guía por orden antes de pasar a Out. Como no existe un Pack independiente, un batch abre su lista de órdenes y cada orden se prepara individualmente.

No se cambian rutas, ubicaciones ni número de pasos del almacén. En tres pasos, las validaciones avanzan los movimientos nativos Existencias → Zona de empaquetado → Salida → Clientes. Los nombres de ubicaciones pueden variar. En un paso, Out conserva los requisitos nativos de la entrega y requiere un paquete o guía para identificarla.

## Recolección móvil: nuevo flujo de esta versión

En la tarjeta **Recolección**, pulse **Operar** para abrir la pantalla móvil. **Abrir operaciones** conserva la lista nativa de Odoo. En el detalle de una operación móvil, **Abrir original** permite volver a su formulario o batch nativo.

### Pantalla 1: panel

Tarjetas táctiles muestran la referencia de operación o batch, el campo **Documento de origen** real (`origin`), tipo de operación y estado. Incluyen el número de órdenes de venta vinculadas y piezas; los batches muestran además cuántas transferencias incluyen. Una operación sin venta vinculada muestra cero órdenes, sin inventar una relación a partir de su origen.

El panel usa el almacén y la fecha elegidos en el tablero. Incluye recolecciones individuales y batches existentes; no obliga a crear un batch para trabajar una operación individual. Los batches se muestran completos, aunque algunas órdenes tengan otra fecha. Un batch que mezcla etapas o almacenes fuera del alcance autorizado queda bloqueado para este flujo. Se muestran 30 tarjetas por página, con búsqueda de origen o referencia dentro de la página y navegación Anterior/Siguiente.

### Pantalla 2: productos por recoger

Cada tarjeta muestra **Ubicación de origen**, **Producto** y **Recoger**, con la cantidad reservada y su unidad. Se respeta la ubicación real de cada línea reservada: si un producto se recoge de distintas ubicaciones, aparecen tarjetas separadas. Se muestran origen del pedido y lote nativo como información auxiliar.

El botón grande **Validar recolección** permanece al pie de la pantalla. Las operaciones en espera pueden consultarse; para validarlas deben estar completamente disponibles. Esta primera pantalla procesa la cantidad completa reservada en unidades enteras, usando la unidad de inventario. Para cantidades parciales, otras unidades, reservas faltantes o ajustes de lotes, use **Abrir original**.

### Captura y validación

Al pulsar Validar recolección aparece una captura móvil por producto/ubicación:

- Capture un **Número de serie / IMEI por pieza**, manualmente o mediante un lector que escriba en el campo y envíe Enter. No se implementa escaneo por cámara en esta versión.
- Si Stock UPC Validation lo exige, capture también el UPC. Su comprobación se delega al módulo instalado, incluyendo los códigos múltiples admitidos por él.
- Si el tipo de operación exige guía, se solicita la guía de cada pedido. En dos pasos, esto permite capturar la información de preparación en Pick.
- **Confirmar y validar** se habilita al completar la captura. Se vuelve a comprobar el almacén autorizado, disponibilidad, cantidades, series y si la reserva cambió desde que se abrió.
- Se rechazan series faltantes y duplicadas en la misma operación. Si el producto tiene seguimiento nativo por serie, el número debe coincidir con su serie reservada. Para productos cuyo lote nativo es una PO, la serie adicional queda vinculada a la línea de ese lote; no sustituye el lote PO.
- Las series se guardan mediante el modelo de `adicional_serial_number` instalado. Las reglas de UPC y la validación de inventario se ejecutan mediante los asistentes/métodos originales. Cualquier asistente adicional de Odoo se conserva; si se cancela, la operación continúa pendiente en el panel.

Las series aún no confirmadas viven en la pantalla; si vuelve al panel o cierra la app antes de confirmar, debe capturarlas de nuevo. Las series ya registradas en Pick se muestran y conservan. Si una preparación que exige guía tiene series previamente registradas pero aún exige su asistente UPC, se deriva al formulario original para revisar ese caso.

Esta versión añade una interfaz Owl adaptable dentro de Odoo, compatible con el espacio web que utiliza su app móvil. No es una aplicación móvil separada ni un modo sin conexión. El ZIP contiene solamente `systore_operations_dashboard`: no incluye copias de los módulos UPC, códigos múltiples o series, y no sustituye sus versiones instaladas.

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

Comprobaciones locales: 31 pruebas Python de fechas, contadores, etapas, paquetes y entradas de series; compilación de las tres plantillas con Owl de Odoo 18; navegación nativa frente a móvil; panel, búsqueda, detalle, capturas, duplicados, reserva cambiada y asistentes del cliente; registro de las tres acciones con el conversor/cargador nativos; sintaxis Python/JavaScript, XML y rutas del manifiesto.

Las pruebas locales usan dobles de ORM y plantillas sin montar un navegador. **No se ejecutó Odoo completo ni la app móvil real.** Las pruebas nativas incluidas en `tests/test_operations_dashboard.py` cubren un batch móvil de dos ventas, UPC incorrecto/correcto, guardado de tres series y validación nativa. Ejecútelas en la rama SH con `--test-enable --test-tags /systore_operations_dashboard --stop-after-init`.

Prueba de aceptación en smartphone: abra Operaciones → Recolección → Operar; revise una operación individual y un batch, sus documentos de origen, ubicaciones y piezas. Pulse Validar recolección; compruebe serie faltante, duplicada, UPC incorrecto y captura correcta. Confirme que el Pick quede hecho y avance la siguiente etapa nativa. Abra también Abrir operaciones para verificar el acceso al formulario original.
