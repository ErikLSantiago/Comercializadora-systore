# Systore - Costos por Lote / Orden de Compra (Odoo 18)

## Qué hace
Agrega una pestaña en **Producto** llamada **"Costos por Lote/OC"** que genera un reporte operativo:

- Lee existencias **por lote** en ubicaciones internas (stock.quant)
- Asume tu estándar: **lote.name == purchase.order.name** (ej. P00001)
- Busca el **costo actual** desde `purchase.order.line.price_unit`
- Calcula **Valor real operativo** = `cantidad disponible × costo OC (actual)`

> **Importante:** No revaloriza inventario ni afecta asientos contables.

## Cómo usar
1. Instala el módulo
2. Abre un producto
3. Ve a la pestaña **Costos por Lote/OC**
4. Da click en **Actualizar**

## Notas / Casos límite
- Si un quant no tiene lote, se reporta como "Sin lote".
- Si no existe una Orden de Compra con nombre igual al lote, se mostrará en "Nota".
- Si la UdM en la OC no coincide con la UdM del producto, se marca una nota para revisión.

## Dependencias
- product
- stock
- purchase


## 18.0.1.0.47
- Agrega configuración Open Box en producto: ¿Es open box? y SKU Origen.
- Para productos Open Box, el desglose por lote/OC toma la línea de compra del SKU origen y calcula el costo operativo con 15% de descuento.


## 18.0.1.0.48
- Agrega **Fecha de ingreso** al desglose por Lote/OC.
- Agrega **Días en inventario**, calculados dinámicamente contra la fecha actual.
- La fecha base es la primera recepción validada desde una ubicación de proveedor hacia una ubicación interna.
- Los traslados entre almacenes no reinician la antigüedad.
- Las líneas en Tránsito muestran 0 días y no tienen Fecha de ingreso hasta que exista recepción.
- Los productos Open Box buscan la recepción del SKU Origen usando el mismo nombre de lote, conservando la antigüedad de la mercancía original.
- Al validar una recepción Proveedor → Interno, el reporte se refresca automáticamente para retirar Tránsito y comenzar a mostrar la antigüedad real.


## v18.0.1.0.49 - Días en ubicación

- Añade la columna **Días en ubicación** al desglose por Lote/OC.
- El contador mide desde cuándo el lote mantiene existencia positiva de forma continua en la ubicación actual.
- Entradas parciales adicionales no reinician el contador. Si el lote sale completamente y vuelve a entrar, el contador comienza de nuevo.
- Las transferencias que tocan ubicaciones internas refrescan automáticamente el reporte.
- **Días en inventario** permanece independiente y continúa contando desde la primera recepción Proveedor → Interno.
