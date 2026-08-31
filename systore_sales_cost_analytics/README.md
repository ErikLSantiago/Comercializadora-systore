# Systore Analytics - Ventas, Facturación y Costos

Versión 18.0.1.0.1 para Odoo 18.

## Objetivo

Consolidar en una sola línea analítica la factura, la orden/origen de venta, los datos comerciales de `sale.order`, el movimiento físico por lote y el costo de la orden de compra asociada.

## Conciliación

- Orden base: patrón `PR-#########` (fallback: primeros 12 caracteres).
- Factura ↔ movimiento: relación nativa de Odoo; fallback por Orden base + SKU.
- Movimiento ↔ compra: Lote + SKU, bajo la regla operativa donde el nombre del lote coincide con el nombre de la OC.
- Estado de venta: `Devolución` cuando la cuenta está clasificada como `Tránsito / devolución bruta`; en los demás casos `Venta`.

## Cambios 18.0.1.0.1

- Añade `Orden de venta / Origen` tomada del movimiento/picking, con fallback al origen de factura.
- Añade `Canal de venta` desde `sale.order.x_studio_canal_venta_1`.
- Añade `Número de orden mkp` desde `sale.order.x_studio_nmero_de_orden_mkp`.
- Muestra `Proveedor` y `Nombre del producto` en el reporte principal.
- Añade `Estado de venta`: Venta / Devolución.
- Retira `Costo asignado` de las vistas del reporte; se conserva únicamente como cálculo técnico interno para Utilidad.
- Deja `Costo unitario` como la única columna de costo visible.
- Corrige Margen %: Odoo recibe ahora la razón decimal esperada por el widget `percentage` (por ejemplo -1.0141 = -101.41%).

## Después de actualizar el módulo

Ejecutar **Systore Analytics → Actualizar reporte** para regenerar el rango que se quiera validar; de esta forma también se recalculan Margen, Canal de venta, Número de orden mkp y Origen.
