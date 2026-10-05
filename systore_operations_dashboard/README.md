# Tablero de operaciones · Odoo 18

Versión **18.0.1.7.0** · Nombre técnico `systore_operations_dashboard`.

## Cambios de 18.0.1.7.0

- Etiquetas **Cajas** y **Lotes**. Se conserva el nombre técnico de los campos para mantener los datos existentes.
- Almacenamiento solo muestra operaciones Listo. **Próximos días** reúne hoy y mañana en la zona horaria del usuario, sumando operaciones únicas; Atrasadas permanece separado. Al pulsarlo se aplica ese intervalo a la consulta.
- **Operar** en Almacenamiento y Transferencias abre un panel móvil con buscador, productos, ubicaciones, cantidades editables y validación mediante `stock.picking.button_validate`. Mantiene permisos, lotes/series, rutas y asistentes de parcialización de Odoo. **Abrir original** conserva el formulario nativo para los detalles de trazabilidad.
- Encabezados móviles en un solo renglón, con texto abreviado visualmente cuando la pantalla es estrecha.
- Salidas muestra tarjetas de paquetes/guías, con el escaneo más reciente primero. Conserva la papelera y **Validar completas**, sin validación automática.

## Cambios anteriores

- Las tarjetas de Ingresos muestran el **Documento de origen** real (`stock.picking.origin`) de las recepciones vinculadas, y el buscador lo incluye. Si una compra tiene varios orígenes se muestran los distintos valores.
- Las piezas registradas en el resumen de productos aparecen en azul y con mayor tamaño.

## Pendientes para el lunes 5 de octubre de 2026

1. Entrega en un paso: ampliar `stock_upc_validation` para exigir UPC y NS/IMEI por pieza en Out, integrado con Números de serie adicionales. Definir cómo se combina esa preparación con el registro y validación manual de paquetes.
2. Entregas de mayoreo en dos pasos: decidir en qué etapa se capturan UPC y series, y qué adaptación requiere `stock_upc_validation`, preservando las rutas nativas.

Estos puntos quedan para análisis y desarrollo posterior; esta versión no modifica el módulo UPC instalado.

- Ingresos abre el resumen de productos y piezas. Puede registrar cualquier producto, confirmar su cantidad/UPC y regresar al resumen. Salir de la captura sin confirmar descarta esa edición. **Finalizar registro** permite revisar y confirmar únicamente lo registrado; los productos sin registrar se envían con cantidad cero para la recepción parcial nativa.
- Salidas ya no valida al escanear: registra paquetes y espera **Validar completas**. Se retira la columna Operación y se añade una papelera para retirar capturas no entregadas. Un paquete retirado puede escanearse nuevamente. No se deshacen entregas ya validadas.
- Empaquetado solo muestra operaciones listas; se excluyen pendientes y en espera.
- Los buscadores de Recolección, Ingresos y Empaquetado incluyen nombre/SKU del producto y UPC principal o múltiple. Pulse Buscar o Enter; la búsqueda se realiza antes de paginar y conserva el alcance autorizado del almacén. El escáner de Salidas sigue identificando paquetes/guías, no productos.

- Empaquetado muestra una tarjeta por producto con sus piezas solicitadas alineadas a la derecha, como Recolección. La validación sigue siendo por pieza. Incluye **Abrir original**.
- Transferencias solo incluye operaciones en estado **Listo** (`assigned`).
- El buscador de Ingresos consulta compra, referencia del proveedor y proveedor antes de paginar; pulse **Buscar** o Enter.
- Ingresos abre directamente una pantalla por producto: cantidad esperada, cantidad recibida manual, UPC y **Siguiente producto**. Al terminar muestra **Confirmar ingreso**.
- Una cantidad cero deja el producto pendiente y no requiere UPC. Los ingresos parciales conservan el asistente nativo para crear la recepción restante. Se ajustan los excedentes que pudiera dejar el asistente instalado al repartir una captura parcial entre varios movimientos del mismo producto.
- Se retira la tabla general de resumen y su botón **Ver detalle**. Las tarjetas y los accesos operativos permanecen.

- Se retira el selector desplegable de almacén del tablero. El almacén se elige al inicio; la flecha **Almacenes** regresa a esa pantalla.
- En Ingresos, **Comprobar UPC** ahora se llama **Registrar UPC**. La persistencia del código mantiene el comportamiento anterior: se registra al confirmar la recepción.
- Transferencias, Empaquetado y Salidas reúnen todas las pendientes en una tarjeta, sin cuadros Hoy/Mañana/Atrasadas. Sus detalles, listas y batches abarcan todas las fechas. Los filtros de fecha se mantienen para Ingresos y Almacenamiento.
- **Empaquetado → Operar** abre el nuevo panel móvil por pedido: UPC por pieza → NS/IMEI adicional → guía → validación nativa.

- La aplicación abre una pantalla de botones con los almacenes autorizados. Seleccione uno para entrar al tablero; **Almacenes** permite volver.
- Un UPC rechazado en las pantallas guiadas muestra únicamente **No coincide UPC/IMEI**. Los errores de permisos o cantidades conservan su explicación.
- Transferencias excluye los tipos nativos In, Pick, Pack y Out.
- **Ingresos → Operar** abre el nuevo panel móvil por compra, con productos, imágenes, cantidades y comprobación UPC antes de avanzar.

- **Siguiente producto** comprueba inmediatamente el UPC con el validador de `stock_upc_validation`. Un código incorrecto deja al usuario en el mismo producto y muestra el error. En el último producto aparece **Comprobar UPC**.
- La pantalla de UPC incorpora imagen y cantidad **Recoger**, sumada para ese producto entre sus ubicaciones. Editar el código retira la marca UPC correcto.
- Las tarjetas de **Lotes** muestran el usuario del campo nativo `stock.picking.batch.user_id`, o **Sin asignar**.
- Recolección tiene un único resumen de todas sus operaciones pendientes, piezas y batches. Se retiran de esa tarjeta los cuadros Hoy, Mañana y Atrasadas. Su detalle y la apertura nativa abarcan todas las fechas; Ingresos y Almacenamiento conservan sus filtros de fecha.

- Recolección excluye borradores en su tarjeta, listas y operación móvil.
- **Operar** abre dos pestañas: **Por procesar** muestra cada recolección individual del almacén, incluida la que pertenece a un batch; **Lotes** muestra únicamente los lotes con recolecciones asignadas. Cambiar de pestaña reinicia la paginación y la búsqueda.
- Las dos pestañas consultan todas las fechas del almacén seleccionado y mantienen el filtro **Completa**. El tablero conserva sus propios filtros de fecha.
- El detalle incorpora la imagen nativa del producto y retira de la pantalla «Lote / serie nativa». Los lotes y su trazabilidad se conservan en Odoo.

- Recepciones se divide en **Ingresos (In)** y **Almacenamiento (Storage)**. Solo aparecen los tipos nativos activos y seleccionados: una recepción de un paso muestra In; dos pasos muestran In y Storage.
- Pick, Pack y Out muestran piezas solicitadas en su unidad de inventario, batches y órdenes de venta. El detalle agrupa las operaciones de cada batch y muestra también sus lotes nativos cuando existen.
- **Pick móvil** muestra completas y agrupa las piezas por producto y ubicación. Ya no solicita ni registra NS/IMEI. La captura de series permanece en Pack.
- Out comienza con una lista vacía para escanear paquetes y registra los paquetes y valida las salidas completas cuando el usuario pulsa Validar completas, conservando los asistentes y controles nativos de Odoo.
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

Se retiraron los textos introductorios: sobre las tarjetas queda únicamente el buscador. Las tarjetas conservan documento de origen, tipo, estado, órdenes y piezas. Por procesar muestra una tarjeta por operación; Lotes muestra una tarjeta por lote.

El filtro utiliza el campo nativo de su módulo UPC **`systore_batch_readiness_state = 'complete'` (Completa)**. Este es el nombre técnico existente, sin la letra «l» adicional de `readliness`. Solo se muestran operaciones pendientes completas del almacén, de cualquier fecha, excluyendo borradores. Para un batch se comprueban todas sus operaciones pendientes: si alguna está parcial, el batch completo queda fuera de este panel. No se valida un subconjunto ocultando sus miembros parciales.

El buscador consulta origen y referencia dentro de la página. Hay 30 tarjetas por página. Los batches incluyen todas sus recolecciones pendientes autorizadas. Si contienen una operación en borrador, no se ofrecen para validar hasta resolver ese borrador en la vista original. Los batches que mezclan etapas o almacenes fuera del alcance autorizado tampoco se ofrecen en esta pantalla. Las vistas nativas permiten revisar estos registros.

### Batch e individual

- **Batch:** se suman las piezas de sus órdenes por **producto + ubicación de origen + unidad**. Si el mismo producto está en dos ubicaciones, aparece una fila por ubicación. El detalle se ordena por producto y ubicación.
- **Individual:** solo se incluyen las piezas y ubicaciones de esa operación. Abrir un ID individual no incorpora otras órdenes aunque pertenezca a un batch.

La imagen se consulta mediante la ruta autenticada de Odoo para la variante del producto. Si no tiene imagen o no carga, se muestra un marcador. La agrupación es de presentación: conserva los IDs de las líneas, sus lotes nativos y los vínculos con las órdenes. No mezcla reservas ni modifica la trazabilidad. Las cantidades a recoger corresponden a las reservas completas; para parciales, otras unidades o ajustes de reserva se conserva **Abrir original**.

### Validación

Recolección **no solicita ni crea números de serie/IMEI adicionales**. Si el módulo UPC instalado exige un código, se captura una vez por producto y se aplica a sus ubicaciones; el módulo original comprueba que el UPC pertenece al producto al pulsar Siguiente producto. Esa comprobación usa una línea virtual y no valida transferencias ni modifica inventario. La confirmación final vuelve a comprobar los códigos y las reservas. Si no exige UPC, el botón valida directamente mediante Odoo.

Antes de validar se comprueban permisos, estado Completa, disponibilidad, cantidades y que las reservas no hayan cambiado. La confirmación delega en los asistentes/métodos originales de UPC y Odoo. Los controles nativos de lotes o series ya reservados siguen vigentes. El flujo de Pack conserva su captura de UPC, NS/IMEI y guía.

La interfaz funciona dentro de Odoo y de su app móvil con conexión. El ZIP contiene solamente el tablero; no incluye copias ni reemplaza los módulos UPC o series instalados.

## Ingresos móvil

En **Ingresos**, pulse **Operar**. El panel respeta la fecha esperada y el filtro del tablero y muestra las compras, proveedor, referencia y cajas. Si una compra tiene varias recepciones, seleccione la operación. Una recepción que consolida varias compras valida todas sus líneas visibles y lo indica antes de confirmar.

Cada pantalla muestra un producto con imagen, demanda, cantidad recibida manual y UPC. La cantidad comienza vacía para que el operador la capture. La captura comprueba el UPC antes de pasar al siguiente producto; cero permite dejarlo pendiente. Al terminar se revisan las cantidades y se pulsa Confirmar ingreso. Se reutilizan los métodos del módulo instalado `stock_upc_validation`: en recepción, un UPC nuevo puede registrarse para el producto; uno asignado a otro producto se rechaza. La comprobación previa revierte cualquier registro provisional; el código se registra al confirmar.

Configure los almacenes de recepción en `systore_upc_receipt_warehouse_ids` y active `systore_require_upc_on_receipt` en el tipo In. La asignación automática de lote desde el origen sigue `systore_auto_lot_from_origin`. Si el módulo instalado no exige UPC para esa recepción, se respetan sus reglas y se validan las cantidades mediante Odoo.

La confirmación conserva los asistentes nativos de recepción parcial y los controles de trazabilidad. Para unidades distintas de la unidad de inventario, utilice **Abrir original**. El panel no incorpora una captura adicional de series; los requisitos nativos de lotes y series siguen vigentes.

## Operar Pack

Pulse **Operar** en Empaquetado. El panel contiene las operaciones del tipo Pack nativo del almacén, de todas las fechas y sin borradores. Cada tarjeta muestra orden, operación, estado, piezas y batch. Si entra desde un batch, seleccione el pedido: cada operación conserva sus propias series y guía. Solo se pueden preparar operaciones completamente disponibles y con la configuración UPC/guía habilitada.

La pantalla muestra las piezas con su imagen. **Validar piezas** inicia la secuencia por unidad: primero comprueba UPC y después solicita NS/IMEI. Un UPC incorrecto muestra **No coincide UPC/IMEI** sin avanzar. Tras capturar todas las piezas solicita el número de guía; **Validar empaquetado** confirma la operación con el asistente original instalado.

Las comprobaciones previas no crean series ni validan inventario. La confirmación final vuelve a comprobar códigos, disponibilidad, permisos y cambios en la operación; delega la creación en `stock.move.line.serial`, las cantidades y la guía al módulo instalado. Los asistentes nativos adicionales se conservan. La pantalla evita repetir un NS/IMEI dentro del mismo empaque. La guía se propaga a Out mediante la lógica instalada.

El panel no convierte los números de serie adicionales en lotes o series nativos: se mantienen los controles de trazabilidad de Odoo. Esta primera pantalla procesa todas las piezas del pedido; para parciales, unidades alternativas o cantidades fraccionarias se conserva el flujo original con **Abrir operaciones**.

## Escanear Out

Abra Salidas para comenzar una sesión vacía del filtro seleccionado, o abra una operación/batch concreto. Escanee un código y presione Enter:

- Si existen paquetes nativos, use sus códigos. Una salida con varios paquetes solo queda habilitada para Validar completas después de escanearlos todos; una guía que cubra varios paquetes no los sustituye.
- Si no existen paquetes nativos, la guía identifica **un paquete por operación de salida**. Para contar varios cajas de una orden, cree los paquetes nativos durante el empaque.
- Se rechazan códigos desconocidos, guías ambiguas, duplicados, operaciones fuera de la sesión y salidas sin disponibilidad. Una salida que mezcla piezas empaquetadas y sueltas exige completar el empaque.
- Cada escaneo actualiza el listado sin validar entregas. La papelera permite retirar registros no entregados. Si Odoo solicita UPC, lotes, series, guía o un asistente adicional, se muestra ese flujo; no se omite. **Validar completas** permite retomar las operaciones ya escaneadas después de resolver un asistente.

La sesión corresponde al operador que la creó y conserva sus escaneos mientras exista el registro transitorio. Al iniciar otra sesión, la lista comienza vacía. Las salidas ya hechas no se pueden entregar nuevamente. El escaneo de un batch abre todas sus operaciones pendientes autorizadas.

## Contadores y fechas

En In y Storage se usa la **Fecha esperada de la compra (`date_planned`)**, la referencia del proveedor (`partner_ref`) y los cajas informativos de la OC. Cajas y piezas se cuentan una sola vez por compra dentro de cada etapa. Piezas representa el total solicitado de productos físicos, no un saldo que disminuya con cada recepción parcial. En recepciones sin compra, se usa la demanda de la operación.

En expediciones y transferencias se usan fecha programada y demanda de movimientos pendientes. Los totales de diferentes etapas no se suman: una misma mercancía puede estar en varias etapas del flujo. Transferencias muestra movimientos internos desde Existencias del almacén hacia cualquier ubicación, sujeto a los tipos seleccionados. Excluye los tipos nativos In, Pick, Pack y Out, además de tipos con código de entrada o salida.

Hoy y Mañana respetan la zona horaria del usuario. Atrasadas usa el día actual; Todas incluye pendientes sin fecha. Se excluyen registros hechos y cancelados. El detalle muestra hasta 60 filas, pero los contadores y la lista completa incluyen todas las operaciones accesibles.

Un batch puede abarcar fechas distintas. Su fila resume las operaciones del filtro; al operarlo se abre el batch completo, para mantener la agrupación nativa. Se comprueba que todas sus operaciones pendientes pertenezcan al almacén y etapa autorizados.

## Seguridad

Los permisos de almacén se verifican en el servidor en cada consulta y operación. Se mantienen reglas de compañía y permisos nativos. El resumen permite al operador de Inventario leer únicamente datos operativos de las compras y los números de venta vinculados, sin dar acceso a precios ni edición de Compras/Ventas.

Consultar el tablero no valida operaciones ni cambia reservas. Abrir una preparación solicita disponibilidad; pulsar Validar o escanear una salida completa sí opera los movimientos. No se cambian los módulos UPC y series suministrados ni sus reglas de validación.

## Verificación

Comprobaciones locales: 38 pruebas Python de fechas, contadores, paquetes, agrupación por producto/ubicación, captura UPC, filtro Completa, exclusión de borradores, pestañas de individuales/batches y alcance individual; compilación de cinco plantillas con Owl de Odoo 18; navegación al tablero conservando filtros, cambio de pestaña y ruta de imagen, UPC incorrecto sin avanzar, cantidades acumuladas por producto y última comprobación, captura UPC compartida entre ubicaciones, validación sin series, errores y asistentes del cliente; registro de acciones con el conversor/cargador nativos; sintaxis Python/JavaScript, XML y manifiesto.

También se verificaron localmente el inicio sin almacén seleccionado y el flujo móvil de Ingresos: selección de recepción, cantidades, UPC rechazado sin avanzar, confirmación y retorno desde asistentes nativos.

También se comprobó el flujo cliente de Pack: UPC por pieza, rechazo sin avanzar, serie, duplicados, guía al final y asistente nativo. La prueba integrada de tres pasos ahora utiliza esta pantalla de Pack a través de sus métodos de servidor.

Estas pruebas usan dobles de ORM y plantillas sin navegador. **No se ejecutó Odoo completo ni la app móvil real.** Las pruebas nativas incluidas en `tests/test_operations_dashboard.py` cubren un batch de dos ventas agrupado en tres piezas, apertura individual limitada, UPC incorrecto/correcto y comprobación UPC sin validar el picking, seguida de confirmación sin crear series en Pick. También incluyen la recepción con comprobación provisional de UPC sin registrarlo y confirmación con lote de origen; estas pruebas de integración quedan pendientes de ejecutar en Odoo. Ejecútelas en la rama SH con `--test-enable --test-tags /systore_operations_dashboard --stop-after-init`.

En smartphone compruebe: flecha al tablero; solo completas; dos órdenes del mismo producto y ubicación sumadas en un batch; ubicaciones distintas separadas; operación individual limitada a sus piezas; validación UPC sin pedir IMEI; siguiente etapa nativa disponible después de validar Pick.

Verificación 18.0.1.6.0: 38 pruebas locales Python, compilación de cinco plantillas, carga de acciones y pruebas cliente de captura secuencial con producto en cero, parcialización, formato agrupado Pack y apertura original. Las pruebas de integración de búsqueda por proveedor y cantidades parciales se incluyen para ejecutar en Odoo.sh; no se ejecutó una instancia real de Odoo ni la app móvil.

Verificación 18.0.1.6.0: pruebas locales del orden libre de captura, descarte de edición, productos sin registrar en cero, asistente parcial, escaneo sin validación automática, compilación de plantillas y carga de acciones. Prueba integrada de entrega actualizada para retirar, volver a escanear y validar manualmente. Odoo.sh y app móvil pendientes de ejecución real.

Verificación 18.0.1.7.0: 40 pruebas Python locales, seis plantillas compiladas con Owl, registro de acciones con el cargador Odoo y pruebas de navegación, cantidades y asistentes de las dos nuevas pantallas. Incluye prueba de integración nativa de Almacenamiento para ejecutar en Odoo.sh. No se ejecutó una instancia real de Odoo ni la app móvil.
