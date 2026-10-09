# Changelog

## 18.0.1.14.2

- Corrige el conteo de NS/IMEI en captura masiva para contar cada renglón, incluso cuando varias piezas pertenecen al mismo producto.
- Acumula correctamente las piezas esperadas si el mismo producto aparece en más de una línea de origen.
- Cuando existe una diferencia real, muestra el detalle de cantidades esperadas y capturadas por producto.

## 18.0.1.14.1

- Corrige la reconstrucción de líneas al alternar captura individual/masiva para conservar siempre el producto esperado.
- Valida que toda línea del wizard provenga de un movimiento de inventario con producto válido.
- Sustituye el error técnico de campo obligatorio por un mensaje claro cuando exista un movimiento inconsistente.
- Mantiene sin cambios el flujo de entregas de 1, 2 y 3 pasos, los parciales/backorders y la omisión por producto sin UPC/EAN.

## 18.0.1.14.0

- Agrega captura masiva opcional en el paso equivalente a Empaque de almacenes de 1, 2 y 3 pasos.
- Agrupa por producto y valida UPC/EAN una sola vez antes de abrir la captura múltiple de NS/IMEI.
- Valida cantidad exacta, valores vacíos, duplicados en la captura y NS/IMEI ya registrados.
- Permite parciales mediante la cantidad **Piezas a procesar**.
- Conserva el modo por pieza existente.
- Agrega **No asignar número de guía** y registra la omisión en el chatter.
- Los productos marcados sin UPC/EAN tampoco generan líneas obligatorias de NS/IMEI.

## 18.0.1.12.2

- Corrige Packing/Empaque para que el check **El producto no cuenta con UPC/EAN** también omita la validación obligatoria de NS/IMEI.
- Bloquea el campo NS/IMEI cuando la línea está marcada como producto sin UPC/EAN.
- Habilita eliminación de líneas en los wizards para procesar parciales.
- Ajusta cantidades procesadas antes de validar para que las líneas eliminadas no se procesen y Odoo mantenga su flujo nativo de backorder.

## 18.0.1.12.1

- Corrige apertura del wizard completo de Empaque con UPC/EAN + NS/IMEI + guía.

## 18.0.1.12.0

- Agrega checkbox por línea **El producto no cuenta con UPC/EAN**.
- Permite omitir validación UPC/EAN sólo en líneas seleccionadas.
- Registra en chatter usuario y productos omitidos.

## 18.0.1.13.0
- Soporte automático para entregas nativas Odoo de 1, 2 y 3 pasos.
- 3 pasos: PICK conserva validación UPC agrupada; PACK usa flujo completo UPC/EAN + NS/IMEI + guía.
- 2 pasos: Recolectar usa flujo completo de Empaque (UPC/EAN + NS/IMEI + guía).
- 1 paso: Orden de entrega usa flujo completo de Empaque (UPC/EAN + NS/IMEI + guía).
- La configuración de Tipos de operación muestra los pasos nativos del almacén, si el tipo es el paso equivalente a Empaque y el flujo Systore aplicado.
- Se conservan checkbox Sin UPC/EAN, omisión de NS/IMEI en esa línea y procesamiento parcial por eliminación de líneas.
