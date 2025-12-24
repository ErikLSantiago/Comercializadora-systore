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
