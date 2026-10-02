# Tablero de operaciones · Odoo 18

Versión **18.0.1.2.1** · Nombre técnico `systore_operations_dashboard`.

## Cambios

- Recepciones se divide en **Ingresos (In)** y **Almacenamiento (Storage)**. Solo aparecen los tipos nativos activos y seleccionados: una recepción de un paso muestra In; dos pasos muestran In y Storage.
- Pick, Pack y Out muestran piezas solicitadas en su unidad de inventario, batches y órdenes de venta. El detalle agrupa las operaciones de cada batch y muestra también sus lotes nativos cuando existen.
- **Pick móvil** muestra completas y agrupa las piezas por producto y ubicación. Ya no solicita ni registra NS/IMEI. La captura de series permanece en Pack.
- Out comienza con una lista vacía para escanear paquetes y valida cada salida al completar sus paquetes, conservando los asistentes y controles nativos de Odoo.
- Se conserva la aplicación independiente Operaciones, la selección de almacén, permisos por usuario, checks de tipos, referencia del proveedor y filtros de fecha. También la corrección del registro de la acción del tablero que originaba el error KeyNotFoundError.

## Instalación y configuración

Actualice el addon existente; no instale una copia con otro nombre. Requiere Odoo 18 y los módulos `stock_picking_batch`, `adicional_serial_number` y `stock_upc_validation`, además de sus dependencias. Use las versiones de UPC y series suministradas para esta integración. Este ZIP contiene únicamente el tablero actualizado.

1. Copie `systore_operations_dashboard` al directorio de addons de su rama de pruebas de Odoo.sh. Actualice la lista de aplicaciones y actualice este módulo. La actualización carga Python, vistas y assets; después recargue el navegador.
2. En cada almacén, marque **Participa en tablero de operaciones**, asigne **Usuarios del tablero** y seleccione **Tipos de operación incluidos**. Solo un administrador de Inventario puede cambiar estas opciones. Si activa nuevas etapas o crea tipos después, márquelos aquí.
3. En los ajustes de Stock UPC Validation, incluya los almacenes que usarán las pantallas guiadas. En Pick active la exigencia de UPC; en Pack active **Exigir guía en empaque**. Registre los UPC principales o múltiples de los productos.
4. **Pick no debe tener activado Exigir guía en empaque.** Esa opción del módulo UPC exige también NS/IMEI; corresponde a Pack. Si la activó en Pick siguiendo la versión anterior, desactívela allí. El tablero informa esa incompatibilidad de configuración sin omitir los controles del módulo instalado. En dos pasos no se inventa una etapa Pack ni se captura NS/IMEI en Pick; el proceso de empaque separado deberá configurarse en Odoo según su flujo.

No se cambian rutas, ubicaciones ni número de pasos del almacén. En tres pasos, las validaciones avanzan los movimientos nativos Existencias → Zona de empaquetado → Salida → Clientes. Los nombres de ubicaciones pueden variar. En un paso, Out conserva los requisitos nativos de la entrega y requiere un paquete o guía para identificarla.

## Recolección móvil

En la tarjeta **Recolección**, pulse **Operar**. **Abrir operaciones** conserva la vista nativa. La flecha del panel vuelve al tablero con el mismo almacén, fecha y filtro. La flecha del detalle regresa al panel; desde la captura UPC vuelve al detalle.

### Panel

Se retiraron los textos introductorios: sobre las tarjetas queda únicamente el buscador. Las tarjetas conservan documento de origen, tipo, estado, órdenes y piezas.

El filtro utiliza el campo nativo de su módulo UPC **`systore_batch_readiness_state = 'complete'` (Completa)**. Este es el nombre técnico existente, sin la letra «l» adicional de `readliness`. Solo se muestran operaciones pendientes completas del almacén y fecha consultados. Para un batch se comprueban todas sus operaciones pendientes: si alguna está parcial, el batch completo queda fuera de este panel. No se valida un subconjunto ocultando sus miembros parciales.

El buscador consulta origen y referencia dentro de la página. Hay 30 tarjetas por página. Los batches incluyen todas sus recolecciones pendientes autorizadas, aunque alguna tenga otra fecha. Los batches que mezclan etapas o almacenes fuera del alcance autorizado tampoco se ofrecen en esta pantalla. Las vistas nativas permiten revisar estos registros.

### Batch e individual

- **Batch:** se suman las piezas de sus órdenes por **producto + ubicación de origen + unidad**. Si el mismo producto está en dos ubicaciones, aparece una fila por ubicación. El detalle se ordena por producto y ubicación.
- **Individual:** solo se incluyen las piezas y ubicaciones de esa operación. Abrir un ID individual no incorpora otras órdenes aunque pertenezca a un batch.

La agrupación es de presentación: conserva los IDs de las líneas, sus lotes nativos y los vínculos con las órdenes. No mezcla reservas ni modifica la trazabilidad. Las cantidades a recoger corresponden a las reservas completas; para parciales, otras unidades o ajustes de reserva se conserva **Abrir original**.

### Validación

Recolección **no solicita ni crea números de serie/IMEI adicionales**. Si el módulo UPC instalado exige un código, se captura una vez por producto y se aplica a sus ubicaciones; el módulo original comprueba que el UPC pertenece al producto. Si no exige UPC, el botón valida directamente mediante Odoo.

Antes de validar se comprueban permisos, estado Completa, disponibilidad, cantidades y que las reservas no hayan cambiado. La confirmación delega en los asistentes/métodos originales de UPC y Odoo. Los controles nativos de lotes o series ya reservados siguen vigentes. El flujo de Pack conserva su captura de UPC, NS/IMEI y guía.

La interfaz funciona dentro de Odoo y de su app móvil con conexión. El ZIP contiene solamente el tablero; no incluye copias ni reemplaza los módulos UPC o series instalados.

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

Comprobaciones locales: 32 pruebas Python de fechas, contadores, paquetes, agrupación por producto/ubicación, captura UPC, filtro Completa y alcance individual; compilación de tres plantillas con Owl de Odoo 18; navegación al tablero conservando filtros, captura UPC compartida entre ubicaciones, validación sin series, errores y asistentes del cliente; registro de acciones con el conversor/cargador nativos; sintaxis Python/JavaScript, XML y manifiesto.

Estas pruebas usan dobles de ORM y plantillas sin navegador. **No se ejecutó Odoo completo ni la app móvil real.** Las pruebas nativas incluidas en `tests/test_operations_dashboard.py` cubren un batch de dos ventas agrupado en tres piezas, apertura individual limitada, UPC incorrecto/correcto y confirmación sin crear series en Pick. Ejecútelas en la rama SH con `--test-enable --test-tags /systore_operations_dashboard --stop-after-init`.

En smartphone compruebe: flecha al tablero; solo completas; dos órdenes del mismo producto y ubicación sumadas en un batch; ubicaciones distintas separadas; operación individual limitada a sus piezas; validación UPC sin pedir IMEI; siguiente etapa nativa disponible después de validar Pick.
