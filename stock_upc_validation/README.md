# Stock UPC Validation

Módulo para validar y registrar UPC/EAN en flujos de almacén, con soporte para recepción, recolección, empaque y salida.

## Versión 18.0.1.14.1

### Cambios incluidos

- Corrección para conservar `product_id` al reconstruir las líneas del wizard al cambiar entre captura individual y masiva.
- Validación preventiva con mensaje claro si un movimiento de inventario no tiene un producto válido asociado.

- Nuevo checkbox **Captura masiva** en el paso equivalente a Empaque.
- En modo masivo se muestra una línea por producto, se valida el UPC/EAN una sola vez y después se abre una segunda ventana con un NS/IMEI por pieza.
- **Piezas a procesar** permite reducir la cantidad para movimientos parciales; los NS/IMEI deben coincidir exactamente con esa cantidad.
- Se rechazan NS/IMEI vacíos, repetidos en la captura o ya registrados.
- Nuevo checkbox **No asignar número de guía**. La omisión se registra en el chatter con el usuario.
- En el wizard de Packing/Empaque, el check **El producto no cuenta con UPC/EAN** ahora omite también la captura obligatoria de **NS/IMEI** para esa línea.
- El campo **NS/IMEI** queda bloqueado cuando se marca el check de producto sin UPC/EAN.
- Se habilitó eliminar líneas en los wizards para soportar movimientos parciales.
- Al eliminar líneas del wizard de recolección/empaque/salida, sólo se procesan las líneas restantes y Odoo conserva su flujo nativo de parcial/backorder.
- Se mantiene el registro en chatter del usuario que omitió la validación UPC/EAN.

## Notas operativas

- Si una línea sí tiene UPC/EAN, seguirá exigiendo validación normal.
- En Packing, si una línea no tiene UPC/EAN, tampoco exigirá NS/IMEI.
- Para procesar parcialmente, elimina del wizard las líneas que no se procesarán en ese momento.
- En captura masiva también puedes reducir **Piezas a procesar** sin eliminar todo el producto.

### Entregas de 1, 2 y 3 pasos (18.0.1.13.0)
El flujo de salida se adapta automáticamente a `delivery_steps` del almacén:
- 3 pasos (`pick_pack_ship`): PICK valida UPC/EAN; PACK valida por pieza UPC/EAN, NS/IMEI y guía.
- 2 pasos (`pick_ship`): Recolectar es el paso equivalente a PACK y valida por pieza UPC/EAN, NS/IMEI y guía.
- 1 paso (`ship_only`): Orden de entrega es el paso equivalente a PACK y valida por pieza UPC/EAN, NS/IMEI y guía.

La selección de almacenes habilitados continúa en Inventario > Configuración. El checkbox por línea "El producto no cuenta con UPC/EAN" omite también NS/IMEI para esa pieza. La eliminación de líneas del wizard conserva el procesamiento parcial/backorder nativo.
