# Changelog

## 18.0.1.7.0

- Sustituido el seller propio por `x_studio_dropshipping_seller_id` y el check
  existente `is_seller_managed`.
- Eliminado definitivamente `mkp_product_cost`; la compra usa `x_seller_cost`.
- Eliminada la actualización transaccional de tarifas de proveedor.
- La confirmación de la venta crea una OC comercial confirmada por hija, sin
  generar una recepción que duplique el inventario ya registrado del seller.
- La factura de proveedor se genera desde esa OC al completar la entrega.
- La entrega completa ahora se valida por cantidades entregadas, no sólo por el
  estado de los pickings.
- Retiradas las declaraciones antiguas de `stock.seller`, `seller.reservation`
  y las reglas de aprovisionamiento que chocaban con los módulos instalados.
- Añadida migración de valores anteriores y limpieza del constraint legado de
  `stock.seller`.

## 18.0.1.6.1

- Añadido el check **Gestionar como seller** en la ficha del contacto, debajo
  de RFC.
- El campo **Seller** de la orden de venta ahora muestra únicamente contactos
  activos que tengan habilitado dicho check y sean compatibles con la compañía.

## 18.0.1.6.0

- Retirada la aplicación y pantalla **Sellers Virtual** con sus menús de Stock
  Sellers y Reservas.
- Retirada la pestaña de reservas de la orden de venta.
- Eliminada la validación que exigía Stock Seller por producto.
- Eliminada la creación, consumo y liberación de reservas virtuales.
- `seller_id` permanece como el contacto proveedor que detona la PO Dropship.
- El costo de compra se obtiene directamente de `mkp_product_cost` en cada línea
  de venta y se transmite a la línea de compra.
- El SKU Seller queda fuera del flujo activo.
- Los modelos históricos se conservan sin menú ni permisos para permitir una
  actualización no destructiva.

## 18.0.1.5.0

- La factura consolidada requiere que todas las hijas estén completamente
  entregadas o canceladas.
- Las órdenes canceladas se excluyen de las líneas facturadas.
- Las entregas pendientes o parciales bloquean la emisión y muestran las hijas
  que todavía deben concluirse.
- Se impide facturar cuando todas las hijas están canceladas.
- Se bloquea la confirmación de nuevas hijas si la Orden padre ya tiene una
  factura consolidada activa.
- Se mantiene una única factura definitiva apta para su posterior timbrado.

## 18.0.1.4.1

- Corregido el desplegable **Seller** de las órdenes hijas.
- La lista ya no queda limitada a contactos con registros previos en **Stock Sellers**.
- Se muestran contactos activos globales o compatibles con la compañía de la orden.
- Se conserva `seller_id` como contacto detonante y proveedor forzado de la PO de cada hija.

## 18.0.1.4.0

- Sustituida la orden padre física por el campo textual **Orden padre**.
- Las órdenes hijas conservan el nombre recibido desde el sistema externo.
- La facturación de cualquier hija reúne todas las líneas del mismo número padre.
- Añadidas validaciones de compatibilidad fiscal y protección contra una segunda factura.
- La factura conserva el número padre y la trazabilidad de cada orden hija.
- Añadida migración de referencias creadas con la versión 18.0.1.3.0.

## 18.0.1.3.0

- Añadida relación entre orden marketplace padre y órdenes seller.
- Añadida numeración consecutiva de órdenes hijas.
- Añadida facturación consolidada desde la orden padre.
- Bloqueada la facturación individual de órdenes hijas.
- Añadido estado agregado de entrega.
- Separada la factura del cliente de la factura de proveedor.
- La factura de proveedor se procesa al completar la entrega del seller.

## 18.0.1.2.0

- Versión base recibida.
