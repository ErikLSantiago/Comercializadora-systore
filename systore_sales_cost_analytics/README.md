# Systore - Analítica Ventas, Facturación y Costos (Odoo 18)

Primera versión del motor analítico que consolida:

1. Facturación (`account.move` / `account.move.line`).
2. Ventas y movimientos físicos (`sale.order`, `stock.move.line`).
3. Lote usado para surtir la operación (`stock.lot`).
4. Compra y costo (`purchase.order`, `purchase.order.line`).

## Reglas implementadas

- **Orden base**: extrae `PR-#########`; si no existe ese patrón, usa los primeros 12 caracteres del origen.
- **Code Orden**: `Orden base + SKU` para auditoría/fallback.
- **Code Cost**: `Lote + SKU` para auditoría/fallback.
- Prioriza relaciones nativas `account.move.line -> sale_line_ids -> stock.move -> stock.move.line`.
- Si no existe relación nativa, busca por **Orden base + SKU**.
- La OC se resuelve con la regla operativa actual **`lote.name == purchase.order.name`**.
- Si está instalado el módulo de costo por lote y el producto es Open Box, reconoce sus campos y aplica la regla de costo del SKU origen menos 15%.
- Cuenta contable configurable como **Venta**, **Tránsito / devolución bruta** u **Otro**.
- La devolución contable (cuenta de tránsito) se mantiene separada del retorno físico desde una ubicación cliente.

## Medidas

- Venta contable = crédito - débito.
- Venta asignada = venta contable distribuida entre los lotes/movimientos de la línea facturada.
- Costo asignado = costo unitario convertido a moneda de compañía × cantidad conciliada.
- Utilidad y margen.

## Uso inicial sugerido

1. Instalar el módulo.
2. En Plan contable, clasificar las cuentas de ventas y tránsito con **Clasificación Systore**.
3. Ir a **Systore Analytics > Actualizar reporte**.
4. Reconstruir primero un rango corto (por ejemplo 2–3 de agosto) y comparar contra el Excel de conciliación.
5. Revisar el filtro **Con incidencias** antes de ampliar el rango.

## Alcance v1

Esta versión busca validar primero el motor de conciliación. Los campos personalizados de costos adicionales (flete, importación, recosteo, etc.) se pueden sumar cuando se identifiquen sus nombres técnicos en la base de Odoo.
