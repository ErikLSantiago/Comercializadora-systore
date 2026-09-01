# Systore Analytics - Ventas, Facturación y Costos

Versión 18.0.1.0.2 para Odoo 18.

## Objetivo

Consolidar factura, orden de venta, movimiento físico por lote y orden de compra sin duplicar piezas cuando una orden se entrega y factura de forma parcial en distintos periodos.

## Conciliación de cantidad

La cantidad facturada es ahora la autoridad del reporte.

1. Se toma `account.move.line.quantity` de la línea de factura.
2. Se localizan los movimientos físicos de la línea de venta/SKU.
3. Los movimientos se ordenan cronológicamente.
4. Se descuentan primero las cantidades que ya fueron consumidas por facturas anteriores de la misma línea de venta. Si no existe vínculo nativo, se usa Orden base + SKU como fallback.
5. De los movimientos restantes se asigna únicamente la cantidad de la factura actual, distribuyéndola por lote en FIFO.
6. Si no existen movimientos suficientes para cubrir las piezas facturadas, la línea queda en `Diferencia de cantidad`.

Ejemplo: una orden con 550 piezas históricamente entregadas no reportará 550 en una factura de 95 piezas; la factura actual conciliará como máximo 95 piezas y conservará los lotes correspondientes a ese tramo.

## Campos 18.0.1.0.2

- Orden de venta factura (Origen): `account.move.invoice_origin`.
- Origen movimiento: se conserva como campo opcional de auditoría.
- Canal de venta: `sale.order.x_studio_canal_venta_1`.
- Número de orden mkp: `sale.order.x_studio_nmero_de_orden_mkp`.
- Nombre del producto: usa `product.product.name` (Producto/Nombre), no `display_name`.
- Piezas facturadas: cantidad de factura distribuida entre los lotes conciliados.
- Costo unitario.
- Costo total = Costo unitario × Piezas facturadas conciliadas.
- Precio de venta unitario = Venta asignada ÷ Piezas facturadas conciliadas.
- Utilidad = Precio de venta unitario − Costo unitario.
- Utilidad total: medida técnica/analítica = Venta asignada − Costo total.
- Margen % = Utilidad unitaria ÷ Precio de venta unitario.
- Estado de venta: Venta / Devolución, según clasificación analítica de la cuenta contable.
- Proveedor.

## Después de actualizar

Ejecutar **Systore Analytics → Actualizar reporte** para regenerar el periodo. Para validar órdenes dosificadas, revisar que la suma de `Piezas facturadas` por línea/factura coincida con la cantidad de la factura y no con el total histórico entregado de la orden de venta.


## 18.0.1.1.0 - Primer tablero
- Nuevo menú **Tablero** con filtros globales por periodo, estado Venta/Devolución, canal, cuenta, cliente, producto y proveedor.
- KPI: Venta bruta, Devoluciones, Venta neta, Costo neto, Utilidad, Margen, Piezas netas y Conciliación.
- Evolución diaria de venta neta, costo y utilidad.
- Rankings por canal, producto y proveedor con drill-down al reporte consolidado.
- Bloque de devoluciones por canal y estado de conciliación.
- Estado comercial automático por cuenta contable: nombres con **Tránsito/Transito** = Devolución; nombres con **Clientes** = Venta. La clasificación manual del plan contable tiene prioridad.
- Devoluciones se muestran como importe absoluto para KPI y se restan de la venta bruta al calcular venta neta.

## v18.0.1.1.1
- Estado Venta/Devolución por contrapartida contable: si la póliza de factura contiene una cuenta 106.xx cuyo nombre contiene "Tránsito", se marca como Devolución.
- Canal de venta calculado desde la cuenta 401.xx: Marketplace, Mayoreo o Empleado según catálogo Systore.
- Tablero: gráficas de pastel de distribución de venta bruta por Canal, Producto y Proveedor.
- Campo técnico visible opcional "Cuenta Tránsito contraparte" para auditoría.


## 18.0.1.1.3
- Se habilita desplazamiento vertical nativo en la pantalla completa del Tablero para visualizar todas las secciones sin modificar el zoom del navegador.
- Se evita scroll horizontal del contenedor principal y se conserva el scroll interno de componentes anchos como Evolución.
