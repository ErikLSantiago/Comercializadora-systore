# Cobranza MKP — v18.0.1.0.29

Módulo independiente para **Odoo 18 Enterprise / Odoo.sh**. Marketplace conserva su historial inalterable por línea de producto y Mayoreo utiliza una captura general separada dentro de la orden de venta.

Esta revisión permite crear una línea de pago sin que el valor temporal cero del editor interrumpa el `onchange` de la orden. El importe definitivo continúa validándose al guardar y Estado de pago se presenta como un desplegable nativo.

El Gasto general se mantiene como información interna de la orden, pero se excluye totalmente del listado, los indicadores y el PDF del estado de cuenta del cliente. El documento utiliza formato A4 vertical y únicamente las celdas del encabezado de la tabla llevan contorno y texto en negritas.

Cada pedido Mayoreo muestra el Estado de cuenta Pendiente mientras su adeudo sea mayor a cero, incluso cuando tenga pagos parciales, retenidos o pendientes. Cambia automáticamente a Pagado cuando el saldo queda totalmente cubierto o existe un saldo a favor. El listado abre con Pendiente aplicado como filtro predeterminado para generar estados de cuenta únicamente de pedidos con adeudo; el usuario puede retirar el filtro para consultar los Pagados.

El PDF incorpora la columna **Orden de venta** y repite su número en cada evento, junto con la Referencia cliente. La columna Documento se conserva para mostrar la orden en la factura o la referencia capturada en cada movimiento. Tipo muestra únicamente Factura, Pago, Nota de crédito, Descuento o Ajuste, sin agregar debajo el estado de pago. La tabla redistribuye sus ocho columnas, reduce espacios internos y aumenta la tipografía para aprovechar mejor la hoja A4 vertical.

La tabla del PDF elimina por completo la cuadrícula y el contorno exterior. El encabezado utiliza un fondo azul institucional sin bordes, las filas alternan fondos claros para guiar la lectura y el total adeudado se presenta en una banda discreta. Se conservan la alineación numérica, los espacios entre movimientos y la hoja A4 vertical.

El encabezado muestra el Contacto de facturación (`partner_invoice_id`) con nombre, dirección, RFC, teléfono y correo disponibles. La exportación valida que todas las órdenes seleccionadas pertenezcan al mismo Cliente de facturación; si la selección mezcla clientes, Odoo muestra un mensaje y no genera el PDF.

Esta revisión conserva campos técnicos de compatibilidad de `18.0.1.0.20` para que la vista de la orden de venta pueda abrirse mientras Odoo reemplaza la vista anterior durante la actualización del módulo.

## Instalación o actualización

1. Crear primero un respaldo o duplicado de la base en staging.
2. Subir la carpeta `mkp_collection_control` completa al repositorio de addons personalizados.
3. Actualizar la lista de aplicaciones y actualizar **Cobranza MKP**.
4. Asignar a los usuarios el perfil **Cobranza MKP / Operador** o **Supervisor**.

## Flujo principal

- **Tipo de venta** permite elegir Marketplace o Mayoreo en el encabezado de la orden.
- El tipo debe definirse antes de capturar cobranza o pagos. Una orden con movimientos ya registrados no puede cambiar a un flujo incompatible.
- En una orden de Ventas, el botón inteligente **Cobranza** abre directamente el historial de sus líneas.
- La primera apertura crea una línea activa por cada renglón de producto; las secciones y notas de la orden se omiten.
- Se copian de Ventas: **SKU, Producto, Cantidad, Unidad, Precio unitario e Importe**.
- El wizard separa **Promociones** (Cupón, Killer y Comisión killer por pieza) de **Comisiones y descuentos** (Comisiones por pieza, Impuestos, Envío, Otras comisiones por pieza y Tipo de cálculo).
- **Comisión cupón** se retira de la interfaz y deja de participar en los cálculos. Su columna técnica histórica se conserva únicamente para permitir una actualización segura desde versiones anteriores.
- **Tipo de cálculo** admite Precalculo o Marketplace.
- **Estado de pago** admite Retenido, Pendiente, Pagado, Cancelado o Reembolso.
- La sección **Cobranza** incorpora directamente los campos editables Importe pagado, Fecha de pago y Referencia de pago; no utiliza una captura o wizard adicional para asignar pagos.
- **Importe pagado** representa el acumulado vigente de la línea. Al modificarlo, Por cobrar se recalcula y se crea una nueva revisión; la versión anterior conserva el importe, fecha y referencia anteriores.
- El historial interno calcula la diferencia entre el acumulado anterior y el nuevo para conservar el detalle de los pagos parciales, con usuario y fecha original de registro.
- Modificar únicamente la Fecha de pago, Referencia de pago, comisiones o estado también genera la revisión histórica correspondiente.
- Los importes pagados de versiones anteriores se migran a una primera línea de detalle para conservar el saldo acumulado.
- La sección **Devoluciones** permite elegir una línea concreta de producto, indicar Fecha de solicitud, Referencia y uno de estos estados: Devolución creada, Nuevo, Open box, Pago por reclamo, Sustracción, Reembolso o Venta.
- **Piezas devueltas** permite indicar las piezas de esa línea. No admite valores negativos, cantidades superiores a las vendidas ni cantidad cuando el estado es Venta.
- En la consulta histórica de una devolución se omite el campo técnico Línea de venta; el wizard conserva el selector Línea de producto para aplicar devoluciones a un producto concreto cuando una orden contiene varias líneas.
- Al elegir otra línea del mismo pedido, el wizard carga su versión activa. Guardar genera una revisión únicamente para ese producto.

## Pagos mayoreo

- En órdenes con Tipo de venta **Mayoreo**, el botón Cobranza y las columnas de comisiones por línea se ocultan.
- La pestaña **Pagos mayoreo** trabaja a nivel general de la orden y no crea registros en el historial de Cobranza Marketplace.
- **Gasto general** es un importe positivo que se descuenta del total de la orden. Puede acompañarse de una referencia o concepto.
- La tabla de pagos permite capturar Fecha de pago, Referencia, Importe, Estado y Comentario.
- Los estados disponibles son Retenido, Pendiente, Pagado, Cancelado y Reembolso.
- Pueden agregarse varios pagos para soportar pagos parciales. Solo los registros Pagados reducen el saldo; los Reembolsos lo incrementan, y Pendientes o Retenidos se muestran por separado.
- Los pagos no se eliminan: si dejan de aplicar deben marcarse como Cancelados. Las modificaciones se registran en el chatter de la orden con sus valores anterior y nuevo.
- `Neto esperado = Total de la orden - Gasto general`.
- `Por cobrar = Neto esperado - Pagos pagados + Reembolsos`.
- Al actualizar desde `18.0.1.0.20`, las capturas generales experimentales de Mayoreo se trasladan a esta pestaña cuando es posible; el historial anterior se conserva sin aparecer en los reportes Marketplace.

## Estado de clientes Mayoreo

- El Dashboard incorpora un resumen independiente de Mayoreo con pedidos, clientes, Monto neto, Monto pagado y Monto adeudado.
- **Estado de clientes Mayoreo** abre un informe de lista por pedido con Cliente, Orden de venta, Referencia del cliente (`client_order_ref`), Total, Gasto general, Monto neto, Monto pagado, Monto adeudado y Fechas de pago.
- La lista permite agrupar por Cliente, Vendedor o Mes del pedido.
- Para generar el documento, seleccione uno o varios pedidos y presione **Generar PDF**. El PDF crea un estado de cuenta separado por cliente y moneda, muestra totales y detalla Fecha, Referencia, Estado e Importe de cada pago.
- Las fechas resumidas consideran pagos con estado Pagado o Reembolso. Los registros Pendientes, Retenidos y Cancelados permanecen visibles en el detalle del PDF.
- El PDF presenta un estado de cuenta cronológico por eventos con las columnas Tipo, Documento, Referencia cliente, Monto neto, Monto pagado, Monto adeudado y Fecha.
- Cada pedido genera una línea Factura con la fecha de la orden. Cada movimiento de Mayoreo genera otra línea en la fecha capturada y el Monto adeudado se recalcula secuencialmente.
- Los tipos manuales son Pago, Nota de crédito, Descuento y Ajuste. Nota de crédito y Descuento requieren importes negativos; Ajuste admite valores positivos o negativos.
- Los pagos efectivos reducen el adeudo. Notas de crédito, descuentos y ajustes Pagados modifican el Monto neto. Los movimientos Pendientes, Retenidos o Cancelados se muestran sin modificar el saldo hasta que correspondan.
- El Gasto general no participa ni se presenta en el estado de cuenta del cliente.
- El resumen superior del PDF muestra Neto, Pagado y Adeudado sin recuadros y el pie muestra el Importe total adeudado del cliente.

## Dashboard

- El icono **Cobranza MKP** abre un tablero propio con segmentadores, indicadores y gráficas de composición.
- **Fecha desde**, **Fecha hasta** y **Mes** usan `invoice_date`, tomando la fecha más reciente de las facturas de cliente no canceladas asociadas a la orden.
- **Cliente** usa `sale.order.partner_invoice_id`.
- **Estado** filtra el Estado de pago.
- Los segmentadores **Killer**, **Cupón** y **Devolución** localizan órdenes con líneas Activas que contengan esos conceptos y conservan todas las líneas activas de las órdenes resultantes para no recortar sus totales.
- El análisis utiliza únicamente las revisiones Activas para no duplicar importes históricos.
- Las tarjetas muestran Base ajustada, Por cobrar, Importe pagado, comisiones, retenciones/impuestos, envío, Cupón, Killer y piezas devueltas.
- La barra global segmenta Importe pagado, Por cobrar, comisiones, envío, retenciones/impuestos, Comisión killer, otras comisiones y Cupón.
- **Próximos pagos o liberaciones** muestra únicamente el Saldo de liberaciones de las líneas Pendientes o Retenidas con Fecha de pago igual o posterior al día actual; no despliega el historial dentro del tablero.
- El Saldo de liberaciones y el botón **Consultar pedidos pendientes de pago** abren los pedidos que forman exactamente ese importe. El filtro Cliente de facturación permite consultar el saldo de un cliente concreto.
- El resumen inferior muestra la cobranza por Estado de pago.
- El tablero utiliza un contenedor de altura limitada con barra de desplazamiento vertical propia para permitir navegar por todos los indicadores y gráficas.
- La tabla dinámica anterior permanece disponible desde **Análisis dinámico**.
- Se puede agrupar también por Tipo de cálculo, Estado de devolución, Orden de venta, Producto y mes de actualización.
- El menú **Historial de cobranza** conserva el reporte detallado y la importación.
- El dashboard y el Historial de cobranza analizan exclusivamente Marketplace; Mayoreo permanece dentro de cada orden de venta.

## Alerta en Ventas

- Una orden con al menos una devolución vigente muestra el botón rojo **Devoluciones**.
- El contador considera productos con Estado de devolución diferente de Venta.
- Al abrirlo se muestran únicamente las líneas activas con devolución de esa orden.
- La línea activa muestra el botón **Modificar**. Al guardar un cambio, la línea anterior queda como Histórica y se genera una nueva línea Activa.
- Si SKU, producto, cantidad, precio unitario o importe cambian en Ventas, al volver a abrir Cobranza se crea otra revisión automáticamente.
- Cada versión conserva usuario, fecha, origen, comentario opcional y vínculo con la versión anterior.
- En cada línea de la orden de venta se muestran como columnas informativas **Comisiones**, **Envío**, **Retenciones** y **Otras comisiones**, obtenidas de la revisión activa de cobranza.

## Cálculos

- `Sub total = Importe - Cupon + Killer`
- `Piezas = valor absoluto de Cantidad`
- `Comisión killer total = Comisión killer por pieza × Piezas`
- `Comisiones totales = Comisiones por pieza × Piezas`
- `Otras comisiones totales = Otras comisiones por pieza × Piezas`
- `Total ajustado = Sub total - Comisión killer total - Comisiones totales - Impuestos - Envío - Otras comisiones totales`
- `Por cobrar = Total ajustado - Importe pagado`

La sección **Cobranza** muestra Sub total y Por cobrar. El campo técnico Total ajustado se conserva para mantener compatibilidad con las revisiones creadas por versiones anteriores.

Al actualizar a esta versión, los valores existentes de Comisión killer, Comisiones y Otras comisiones se interpretan como importes unitarios y los saldos almacenados se recalculan con la Cantidad de cada línea. Revise el resultado primero en staging.

## Importación de comisiones

- En **Historial de cobranza**, el engrane de acciones incluye **Importar registros**, igual que en las listas nativas de Odoo.
- La vista mantiene habilitada la capacidad de creación requerida por el cliente web de Odoo para mostrar esa acción; el modelo intercepta la carga y la convierte en revisiones históricas, sin permitir edición ni eliminación ordinaria.
- Admite archivos CSV y XLSX con la pantalla estándar de carga, prueba y mapeo de columnas.
- Cada fila se identifica mediante **Orden de venta + Producto** o **Orden de venta + SKU**.
- La importación de este reporte solo acepta órdenes Marketplace. Los pagos Mayoreo se registran manualmente en su pestaña independiente.
- Si el producto o SKU aparece varias veces en una orden, debe agregarse la columna **Secuencia** de la línea de venta.
- Solo se actualizan las columnas presentes en el archivo. Cada fila importada crea una nueva revisión Activa y conserva la anterior como Histórica.
- Se pueden importar Cupón, Killer, Comisión killer, Comisiones, Impuestos, Envío, Otras comisiones, Tipo de cálculo, Estado de pago, Fecha de pago, Importe pagado, Referencia de pago y Comentario.
- En el template, Comisión killer, Comisiones y Otras comisiones se informan como valores unitarios por pieza. Impuestos y Envío continúan siendo importes totales de la línea.
- El mismo template permite actualizar el acumulado de Importe pagado junto con Fecha de pago y Referencia de pago. Cada fila crea una revisión histórica igual que una modificación manual.
- Cuando la importación aumenta el Importe pagado, la diferencia genera automáticamente el detalle del pago parcial con la fecha y referencia de esa fila.
- También pueden mapearse los campos de devolución cuando se requiera una actualización masiva.
- No utilice ID externo para reemplazar registros históricos: cada fila representa una actualización y debe producir una revisión nueva.

Los cálculos de Marketplace se realizan por línea. El historial completo puede consultarse también desde el icono **Cobranza MKP** del inicio.

## Compatibilidad con versiones anteriores

- Los eventos, pagos, importaciones y datos generales capturados antes de esta versión no se eliminan.
- Al crear por primera vez el historial por producto, los importes generales existentes se distribuyen proporcionalmente entre las líneas para conservar sus totales.
- Las pantallas anteriores permanecen fuera de la navegación principal mientras se termina de definir el nuevo flujo.

## Alcance

No genera asientos contables, pagos bancarios, facturas, notas de crédito ni movimientos de inventario. Es un control manual y auditable.

**IMPORTANTE:** esta compilación pasa validaciones estáticas Python/XML y pruebas unitarias de cálculos sin una instalación local de Odoo. Debe instalarse primero en staging de Odoo.sh.
