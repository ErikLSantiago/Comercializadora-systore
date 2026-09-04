# Wholesale Allocation

## Objetivo
Primera fase para operaciones de mayoreo en Odoo 18.

## Qué hace
- Agrega **Associated Purchase Orders** en la orden de venta.
- Sólo aplica al almacén configurado en Ajustes de Inventario.
- La reserva automática intenta omitir lotes cuyo nombre no coincida con las órdenes de compra asociadas.
- Permite usar lotes externos de forma manual en la entrega.
- Marca las líneas manuales externas con el booleano **Manual External Lot**.

## Configuración
1. Instalar el módulo.
2. Ir a **Inventario > Configuración > Ajustes**.
3. Seleccionar el almacén en **Wholesale allocation warehouse**.
4. En las ventas de ese almacén, usar la pestaña **Wholesale Allocation** para asociar las órdenes de compra.

## Nota técnica
Esta versión está pensada como una **fase 1 conservadora**. La restricción se introduce en la capa de reserva automática, sin bloquear capturas manuales. Dependiendo de personalizaciones previas y del nivel de trazabilidad configurado para los productos, puede requerirse una segunda fase para una asignación más estricta por cantidad / por línea.
