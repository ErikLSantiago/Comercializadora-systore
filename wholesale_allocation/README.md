# Wholesale Allocation

## Fase 1 - versión 18.0.1.4.0

### Funciones
- Los almacenes pueden marcarse como **Wholesale**.
- La reserva automática de ventas Wholesale utiliza únicamente lotes cuyo nombre coincida con las Órdenes de Compra asociadas.
- Los lotes externos siguen pudiendo agregarse manualmente.
- Cada almacén Wholesale puede activar **Exigir OC asociada al confirmar ventas**.
- Si esa opción está activa, Odoo bloquea la confirmación de la venta cuando `associated_purchase_order_ids` está vacío.
- La Orden de Compra muestra un smart button **Ventas asociadas** que abre las ventas vinculadas a esa OC.

### Configuración
1. Inventario > Configuración > Almacenes.
2. Abrir el almacén correspondiente.
3. Activar **Wholesale**.
4. Activar o desactivar **Exigir OC asociada al confirmar ventas** según la política del almacén.

### Uso
En una venta de un almacén Wholesale, abrir la pestaña **Wholesale Allocation** y seleccionar una o más Órdenes de Compra asociadas. La relación también queda visible desde cada Orden de Compra mediante el smart button **Ventas asociadas**.

Version 18.0.1.5.0
------------------
- Purchase Orders routed to a warehouse marked Wholesale now show an allocation badge.
- "Sin asignar" is shown in red when the PO is not linked to any Sale Order.
- "Asignada" is shown in green once at least one Sale Order links the PO.
- The badge is available in the Purchase Order form and Purchase Order list views.
