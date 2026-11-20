# Marketplace Seller Dropship Bridge

Versión 18.0.1.7.0 para Odoo 18.

## Flujo multiseller

- La orden padre no se crea como orden de venta en Odoo.
- Cada orden hija recibe del sistema externo su nombre (`1001-1`, `1001-2`) y el
  campo textual **Orden padre** (`1001`).
- Odoo nunca renombra las órdenes hijas.
- Al facturar cualquiera de las hijas, el módulo localiza todas las órdenes de
  la misma compañía con el mismo número padre y crea una sola factura.
- Antes de consolidar se validan estado, cliente, contacto de facturación,
  compañía, moneda, posición fiscal y plazo de pago.
- Si ya existe una factura consolidada activa, no se permite crear una segunda.
- Cada línea de factura conserva el vínculo estándar con su línea y orden seller original.
- Cada hija muestra el estado agregado de entrega de la operación.
- La factura de proveedor de cada seller se crea y publica cuando la entrega de esa orden hija queda completa.
- El seller se toma del campo existente `x_studio_dropshipping_seller_id` de la
  orden y debe tener activo `is_seller_managed` (**Gestionar como Seller**).
- Al confirmar cada hija se crea y confirma una OC comercial vinculada, sin
  generar otra recepción porque la mercancía ya existe en la ubicación interna
  del seller.
- El costo de la OC y de la factura de proveedor se toma exclusivamente de
  `sale.order.line.x_seller_cost`.
- El módulo no modifica tarifas de proveedor (`product.supplierinfo`).
- `stock.seller` pertenece al módulo instalado `stock_sellers`; este puente no
  vuelve a declarar ese modelo ni sus reservas antiguas.

## Regla de facturación definitiva

- La factura consolidada sólo puede crearse cuando todas las órdenes hijas de
  la misma **Orden padre** están completamente entregadas o canceladas.
- Una hija pendiente o parcialmente entregada bloquea la facturación e informa
  cuáles órdenes faltan por concluir.
- Las hijas canceladas se consideran concluidas, pero sus líneas se excluyen de
  la factura.
- Debe existir al menos una hija completamente entregada.
- Después de crear una factura consolidada activa no se permite confirmar una
  nueva hija del mismo número padre ni generar otra factura.
- Una entrega parcial con remanente cancelado no se considera completa: las
  cantidades entregadas deben cubrir las cantidades solicitadas.

## Compatibilidad de actualización

La migración copia valores útiles de los campos anteriores a los campos ya
existentes de Doto y retira del código las declaraciones que chocaban con
`stock_sellers`. Las órdenes sin Orden padre también crean su OC comercial
desde el seller informado y `x_seller_cost`.
