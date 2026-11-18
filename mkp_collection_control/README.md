# Cobranza MKP — v18.0.1.0.15

Módulo independiente para **Odoo 18 Enterprise / Odoo.sh**. Esta versión organiza la cobranza como un historial inalterable por línea de producto de la orden de venta.

## Instalación o actualización

1. Crear primero un respaldo o duplicado de la base en staging.
2. Subir la carpeta `mkp_collection_control` completa al repositorio de addons personalizados.
3. Actualizar la lista de aplicaciones y actualizar **Cobranza MKP**.
4. Asignar a los usuarios el perfil **Cobranza MKP / Operador** o **Supervisor**.

## Flujo principal

- En una orden de Ventas, el botón inteligente **Cobranza** abre directamente el historial de sus líneas.
- La primera apertura crea una línea activa por cada renglón de producto; las secciones y notas de la orden se omiten.
- Se copian de Ventas: **SKU, Producto, Cantidad, Unidad, Precio unitario e Importe**.
- El wizard separa **Promociones** (Cupón, Killer y Comisión killer) de **Comisiones y descuentos** (Comisiones, Impuestos, Envío, Otras comisiones y Tipo de cálculo).
- **Comisión cupón** se retira de la interfaz y deja de participar en los cálculos. Su columna técnica histórica se conserva únicamente para permitir una actualización segura desde versiones anteriores.
- **Tipo de cálculo** admite Precalculo o Marketplace.
- **Estado de pago** admite Retenido, Pendiente, Pagado, Cancelado o Reembolso.
- La sección **Cobranza** incorpora **Referencia de pago**, **Fecha de pago** e **Importe pagado**.
- La Fecha de pago admite tanto la fecha confirmada como la tentativa y Odoo la presenta de acuerdo con el idioma del usuario (`dd/mm/aaaa` en español).
- Importe pagado es acumulado por línea y permite registrar pagos parciales. Cada ajuste genera una revisión histórica nueva.
- La sección **Devoluciones** permite elegir una línea concreta de producto, indicar Fecha de solicitud, Referencia y uno de estos estados: Devolución creada, Nuevo, Open box, Pago por reclamo, Sustracción, Reembolso o Venta.
- **Piezas devueltas** permite indicar las piezas de esa línea. No admite valores negativos, cantidades superiores a las vendidas ni cantidad cuando el estado es Venta.
- En la consulta histórica de una devolución se omite el campo técnico Línea de venta; el wizard conserva el selector Línea de producto para aplicar devoluciones a un producto concreto cuando una orden contiene varias líneas.
- Al elegir otra línea del mismo pedido, el wizard carga su versión activa. Guardar genera una revisión únicamente para ese producto.

## Dashboard

- El icono **Cobranza MKP** abre un tablero propio con segmentadores, indicadores y gráficas de composición.
- **Fecha desde**, **Fecha hasta** y **Mes** usan `invoice_date`, tomando la fecha más reciente de las facturas de cliente no canceladas asociadas a la orden.
- **Cliente** usa `sale.order.partner_invoice_id`.
- **Estado** filtra el Estado de pago.
- Los segmentadores **Killer**, **Cupón** y **Devolución** localizan órdenes con líneas Activas que contengan esos conceptos y conservan todas las líneas activas de las órdenes resultantes para no recortar sus totales.
- El análisis utiliza únicamente las revisiones Activas para no duplicar importes históricos.
- Las tarjetas muestran Base ajustada, Por cobrar, Importe pagado, comisiones, retenciones/impuestos, envío, Cupón, Killer y piezas devueltas.
- La barra global segmenta Importe pagado, Por cobrar, comisiones, envío, retenciones/impuestos, Comisión killer, otras comisiones y Cupón.
- **Próximos pagos o liberaciones** muestra las líneas Pendientes o Retenidas con Fecha de pago igual o posterior al día actual. Incluye un resumen por Cliente de facturación y el detalle de fecha, orden, producto, estado, referencia y saldo.
- El resumen inferior muestra la cobranza por Estado de pago.
- El tablero utiliza un contenedor de altura limitada con barra de desplazamiento vertical propia para permitir navegar por todos los indicadores y gráficas.
- La tabla dinámica anterior permanece disponible desde **Análisis dinámico**.
- Se puede agrupar también por Tipo de cálculo, Estado de devolución, Orden de venta, Producto y mes de actualización.
- El menú **Historial de cobranza** conserva el reporte detallado y la importación.

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
- `Total ajustado = Sub total - Comisión killer - Comisiones - Impuestos - Envío - Otras comisiones`
- `Por cobrar = Total ajustado - Importe pagado`

La sección **Cobranza** muestra Sub total y Por cobrar. El campo técnico Total ajustado se conserva para mantener compatibilidad con las revisiones creadas por versiones anteriores.

## Importación de comisiones

- En **Historial de cobranza**, el engrane de acciones incluye **Importar registros**, igual que en las listas nativas de Odoo.
- La vista mantiene habilitada la capacidad de creación requerida por el cliente web de Odoo para mostrar esa acción; el modelo intercepta la carga y la convierte en revisiones históricas, sin permitir edición ni eliminación ordinaria.
- Admite archivos CSV y XLSX con la pantalla estándar de carga, prueba y mapeo de columnas.
- Cada fila se identifica mediante **Orden de venta + Producto** o **Orden de venta + SKU**.
- Si el producto o SKU aparece varias veces en una orden, debe agregarse la columna **Secuencia** de la línea de venta.
- Solo se actualizan las columnas presentes en el archivo. Cada fila importada crea una nueva revisión Activa y conserva la anterior como Histórica.
- Se pueden importar Cupón, Killer, Comisión killer, Comisiones, Impuestos, Envío, Otras comisiones, Tipo de cálculo, Estado de pago, Fecha de pago, Importe pagado, Referencia de pago y Comentario.
- También pueden mapearse los campos de devolución cuando se requiera una actualización masiva.
- No utilice ID externo para reemplazar registros históricos: cada fila representa una actualización y debe producir una revisión nueva.

Los cálculos se realizan por línea. El historial completo puede consultarse también desde el icono **Cobranza MKP** del inicio.

## Compatibilidad con versiones anteriores

- Los eventos, pagos, importaciones y datos generales capturados antes de esta versión no se eliminan.
- Al crear por primera vez el historial por producto, los importes generales existentes se distribuyen proporcionalmente entre las líneas para conservar sus totales.
- Las pantallas anteriores permanecen fuera de la navegación principal mientras se termina de definir el nuevo flujo.

## Alcance

No genera asientos contables, pagos bancarios, facturas, notas de crédito ni movimientos de inventario. Es un control manual y auditable.

**IMPORTANTE:** esta compilación pasa validaciones estáticas Python/XML y pruebas unitarias de cálculos sin una instalación local de Odoo. Debe instalarse primero en staging de Odoo.sh.
