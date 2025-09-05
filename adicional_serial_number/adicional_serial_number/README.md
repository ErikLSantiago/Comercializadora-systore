Adicional Serial Number
======================

Versión: 18.0.1.1

Propósito
---------
Captura **opcional** de números de serie por operación, sin alterar la trazabilidad nativa (lotes/series).

Puntos clave
------------
- Botón inteligente en `stock.picking` → pegar N seriales → distribución por líneas según cantidades.
- Modelo propio `stock.move.line.serial` enlazado a líneas de movimiento.
- Reporte/menú de historial.
- Parametría `adicional_serial_number.version` para validar upgrades.

Historial de cambios
--------------------
- 18.0.1.1: Renombrado del módulo, vistas `<list>`, eliminación de xpath conflictivo en `stock.move.line` form, versión en Ajustes.

- 18.0.1.3: Removidos attrs/states del wizard; validación de producto en Python.
