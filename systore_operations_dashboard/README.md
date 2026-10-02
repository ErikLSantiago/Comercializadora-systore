# Tablero de operaciones · Odoo 18

Versión: **18.0.1.0.2**. Nombre técnico: `systore_operations_dashboard`.

## Cambios de esta versión

- Recepciones muestra la referencia del proveedor (`partner_ref`) y **Piezas** en lugar del conteo de operaciones. El detalle incluye los totales de bultos y piezas del filtro.
- **Piezas** corresponde al total solicitado de productos físicos de la compra, expresado en la unidad de inventario de cada producto. Se excluyen servicios, secciones y notas; se cuenta una sola vez por compra. No es una cantidad pendiente que se descuente con cada recepción parcial.
- Expediciones se divide en **Recolección (Pick)**, **Empaquetado (Pack)** y **Salidas (Out)**. Solo aparecen las etapas nativas activas cuyos tipos estén seleccionados en el almacén.
- Las tres etapas de expedición muestran **Orden de venta**, obtenida de los vínculos nativos de los movimientos y grupos. No se interpreta el texto libre de Documento de origen.
- En cada almacén se agregó **Tipos de operación incluidos**, una lista de casillas para seleccionar qué tipos participan. Por defecto se seleccionan los tipos activos de la compañía para mantener el funcionamiento anterior; desmarque los que no desea consultar. Los tipos nuevos creados después deben marcarse en esta configuración.
- Los tipos de otros almacenes de la misma compañía se pueden seleccionar para mostrar traslados cuyo origen real sea Existencias del almacén consultado. La casilla autoriza el tipo en el tablero: no cambia sus rutas ni su configuración nativa.

## Corrección de carga conservada

- Aplicación independiente **Operaciones** en el menú principal de Odoo, con icono propio y acceso directo al tablero. Se conserva el nombre técnico del módulo para actualizar la instalación anterior y sus configuraciones; no se necesita instalar un segundo addon.
- Corrección de `KeyNotFoundError: Cannot find key "systore_operations_dashboard.dashboard" in the "actions" registry`: el import de `luxon` de la primera versión generaba una dependencia de módulo inexistente. En Odoo 18, Luxon se proporciona como librería global; ahora se utiliza esa librería.
- Se comprobó el registro de la acción ejecutando JavaScript transformado por el conversor nativo de Odoo 18, además de las pruebas de fechas, agregaciones y plantilla.

## Actualizar desde una versión anterior

1. Sustituya la carpeta del módulo en el repositorio por la incluida en este ZIP y espere a que la rama de Odoo.sh termine de reconstruirse.
2. En Aplicaciones, actualice **Systore · Tablero de operaciones**. Es una actualización de la misma aplicación: no desinstale el módulo anterior.
3. Recargue el navegador con **Ctrl + F5** para cargar el JavaScript nuevo.
4. Abra **Operaciones → Tablero de operaciones** desde el menú principal.
5. Revise **Tipos de operación incluidos** en cada almacén y desmarque los tipos que no desea mostrar.

Se conservan los almacenes participantes, los usuarios asignados y los bultos capturados. La actualización mueve el acceso anterior de Inventario a la aplicación Operaciones.

## Instalación en Odoo.sh

1. Descomprima el ZIP y coloque la carpeta `systore_operations_dashboard` dentro del directorio de addons del repositorio. No suba el ZIP como sustituto de la carpeta.
2. Espere la actualización de la rama de pruebas. Actualice la lista de aplicaciones y busque **Systore · Tablero de operaciones**; quite el filtro «Aplicaciones» si no aparece.
3. Instale el módulo. Sus dependencias son `web`, `purchase_stock` y `sale_stock`, módulos nativos. No requiere Surplus ni cambia reglas de stock.
4. En **Inventario → Configuración → Almacenes**, marque **Participa en tablero de operaciones**, seleccione **Usuarios del tablero** y revise **Tipos de operación incluidos** en cada almacén participante.
5. Asigne a los operadores el permiso nativo de Usuario de Inventario. También deben tener acceso a la compañía del almacén y seleccionarla entre las compañías activas.
6. Entre en **Operaciones → Tablero de operaciones** desde el menú principal de Odoo.

No se habilita ningún almacén automáticamente. Si no hay usuarios asignados, el almacén no aparece, incluso para un administrador de Inventario. La asignación limita el tablero; no sustituye ni amplía las reglas de acceso de Inventario.

## Compras y bultos

El campo nuevo **Bultos esperados** se encuentra junto a la **Fecha esperada** de la orden de compra. Permite cero y números enteros positivos, se puede completar después de confirmar la compra y registra cambios en el chatter.

Los bultos son informativos, sin dimensiones. No crean paquetes físicos de inventario. Cero significa que no se ha informado una cantidad de bultos o que la cantidad informada es cero.

Cada orden de compra con operaciones de recepción pendientes cuenta una vez en el resumen y una vez en el detalle, aunque tenga recepción, almacenamiento o recepciones parciales. Sus bultos y piezas solicitadas se suman una sola vez por almacén y filtro. La referencia del proveedor muestra directamente `partner_ref` de cada compra.

Los bultos representan el total informado en la compra. No se descuentan al validar una recepción parcial. Si la compra tiene operaciones pendientes en dos almacenes, aparece en cada almacén involucrado; los resúmenes entre almacenes no son acumulables.

## Secciones

| Sección | Operaciones incluidas | Fecha para los filtros |
| --- | --- | --- |
| Recepciones | Tipos nativos de Recepción y Almacenamiento del almacén; también Calidad si se usa. El destino debe pertenecer al almacén. | `purchase.order.date_planned` de cada compra vinculada. Si no hay compra vinculada, fecha programada de la operación. |
| Transferencias | Operaciones cuyo origen es Existencias del almacén o una sububicación, hacia cualquier destino. | `stock.picking.scheduled_date`. |
| Recolección (Pick) | Tipo nativo Pick del almacén, si está activo y seleccionado. | `stock.picking.scheduled_date`. |
| Empaquetado (Pack) | Tipo nativo Pack del almacén, si está activo y seleccionado. | `stock.picking.scheduled_date`. |
| Salidas (Out) | Tipo nativo Out del almacén, si está activo y seleccionado. | `stock.picking.scheduled_date`. |

Recepciones admite flujos de uno y dos pasos, además del flujo nativo de tres pasos. En entrega de un paso aparece Salidas; en dos pasos, Recolección y Salidas; en tres pasos, Recolección, Empaquetado y Salidas. Las casillas de tipos de operación permiten excluir cualquiera de estas etapas. El filtro de tipos se aplica también en las acciones de apertura, no solo en los contadores.

Los traslados se atribuyen al almacén por su ubicación origen, aunque su tipo de operación pertenezca al almacén destino. Transferencias puede incluir Pick o una entrega directa porque también salen de Existencias. Las secciones son vistas de trabajo y sus totales no deben sumarse entre sí.

No hay tratamiento especial de Surplus, rutas, nombres de lotes, origen de documentos ni nombres de compras escritos como texto. Un traslado generado por otro módulo se muestra si cumple el criterio de ubicación origen. Las compras de una recepción se identifican mediante los vínculos nativos de los movimientos y hasta dos niveles de movimientos precedentes.

Los tipos de operación personalizados independientes de los tipos nativos configurados en el almacén no se agregan automáticamente a Recepciones ni a Expediciones. Sí pueden aparecer en Transferencias cuando cumplen el criterio de origen.

## Fecha y pendientes

- **Hoy** y **Mañana** usan la zona horaria del usuario en Odoo. Configure `America/Mexico_City` para operar con fechas de México.
- **Consultar fecha** permite elegir cualquier fecha de estimación.
- **Atrasadas** muestra fechas anteriores al día actual, no anteriores a la fecha seleccionada.
- **Todas** incluye todas las operaciones pendientes, incluso sin fecha.
- **Sin fecha** permite revisar registros pendientes sin fecha. Si una recepción tiene compra vinculada y esa compra no tiene Fecha esperada, se clasifica aquí.
- Se excluyen operaciones hechas y canceladas. Se incluyen borradores, en espera, confirmadas y listas para validar.
- Una compra sigue pendiente en Recepciones mientras tenga almacenamiento pendiente, aunque la entrada inicial ya esté hecha. Conserva su Fecha esperada de compra y puede aparecer como atrasada hasta completar el flujo.
- Si una misma operación reúne varias compras con fechas distintas, cada compra se cuenta en su propia fecha. La lista nativa muestra la fecha esperada más temprana y la suma de bultos de todas las compras vinculadas a esa operación.
- Las devoluciones a proveedor no son recepciones. Las devoluciones de cliente que utilicen el tipo nativo de Recepción pueden aparecer como operaciones sin compra.

## Trabajar operaciones

**Abrir operaciones** muestra la lista completa de operaciones pendientes de la sección y fecha seleccionadas. En el detalle, **Operar** abre el formulario nativo cuando hay una operación; si una compra tiene varias, abre su lista filtrada.

En el formulario nativo se pueden registrar cantidades, lotes y números de serie, comprobar disponibilidad y validar con los permisos normales de Odoo. Se mantienen los asistentes de entrega parcial, las validaciones de otros módulos y las restricciones actuales de operación.

La lista nativa muestra operación, etapa, compras, referencia del proveedor, orden de venta, fecha esperada, bultos OC, piezas OC, fecha programada, contacto, ubicaciones y estado. En esta lista una compra puede repetirse por tener varias operaciones: **no sume Bultos OC ni Piezas OC como si fueran cantidades distintas**. El resumen del tablero, el detalle por compra y su pie de totales ya eliminan esas duplicaciones. Para recepciones sin compra, Piezas en el tablero corresponde a la demanda de la operación.

El detalle de la pantalla muestra las primeras 60 filas; **Abrir lista completa** permite operar todas. Los contadores incluyen todos los registros pendientes accesibles, no solo esas primeras filas.

Pulse **Actualizar** al regresar de una operación para volver a consultar los estados y las cantidades. El cambio de fecha o almacén también consulta nuevamente los datos.

## Seguridad y alcance

La comprobación de almacén y usuario se realiza en el servidor en cada consulta y apertura; no se limita a ocultar opciones en la pantalla. Solo un administrador de Inventario configura la participación y la lista de usuarios.

El tablero respeta las reglas de compañía y de lectura de operaciones. Los operadores de Inventario pueden leer en el resumen únicamente los datos operativos de las compras vinculadas a sus recepciones: número, proveedor, referencia del proveedor, fecha esperada, bultos y piezas. También ven el número de venta vinculado a sus expediciones. Esto no otorga acceso a precios ni autorización para modificar o abrir Compras o Ventas.

El módulo no cancela documentos, crea compras, confirma ventas ni modifica movimientos al consultar el tablero. No cambia reservas, rutas, costos ni el método de valoración.

## Pruebas

Comprobaciones realizadas antes de empaquetar: sintaxis Python y JavaScript; XML y rutas de herencia contra las vistas nativas de Odoo 18; compilación de la plantilla con Owl de Odoo 18; límites de fecha y zona horaria; seis pruebas de agregación de bultos y piezas, referencia del proveedor y selección de etapas; y pruebas de la pantalla para cinco secciones, cambio de etapas visibles, filtros, apertura y estados de carga, error y ausencia de almacenes. Se comprobó además el registro de la acción con el conversor y cargador nativos de Odoo 18. Las pruebas de pantalla evalúan el componente y la plantilla sin montar un navegador ni conectarse a Odoo.

Se incluyen pruebas de integración para Odoo en `tests/test_operations_dashboard.py`:

- Recepción de dos pasos sin duplicar compras ni bultos.
- Cambio de fecha esperada y rechazo de bultos negativos.
- Almacenes deshabilitados, usuarios no asignados y protección de configuración.
- Apertura del formulario nativo y rechazo de IDs ajenos al filtro.
- Operador de Inventario sin grupo de Compras.
- Transferencias por origen y etapas de Expediciones.
- Referencia del proveedor, piezas y exclusión de tipos mediante casillas.
- Número de venta en todos los pasos del flujo de salida.
- Límites de fecha en la zona horaria de México.

Para ejecutarlas en un entorno Odoo de pruebas, instale con `--test-enable --test-tags /systore_operations_dashboard --stop-after-init`. Estas pruebas requieren una base de Odoo y no se han ejecutado en su instancia de Odoo.sh.

Antes de pasar a producción, pruebe en su rama SH con una compra de dos pasos, una recepción parcial, una entrega de tres pasos y un operador asignado a un solo almacén. Compruebe también las validaciones de sus módulos de UPC y números de serie.
