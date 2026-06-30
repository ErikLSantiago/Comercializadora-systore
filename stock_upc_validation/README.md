# Stock UPC Validation

Módulo para validar y registrar UPC/EAN en flujos de almacén, con soporte para recepción, recolección, empaque y salida.

## Versión 18.0.1.12.2

### Cambios incluidos

- En el wizard de Packing/Empaque, el check **El producto no cuenta con UPC/EAN** ahora omite también la captura obligatoria de **NS/IMEI** para esa línea.
- El campo **NS/IMEI** queda bloqueado cuando se marca el check de producto sin UPC/EAN.
- Se habilitó eliminar líneas en los wizards para soportar movimientos parciales.
- Al eliminar líneas del wizard de recolección/empaque/salida, sólo se procesan las líneas restantes y Odoo conserva su flujo nativo de parcial/backorder.
- Se mantiene el registro en chatter del usuario que omitió la validación UPC/EAN.

## Notas operativas

- Si una línea sí tiene UPC/EAN, seguirá exigiendo validación normal.
- En Packing, si una línea no tiene UPC/EAN, tampoco exigirá NS/IMEI.
- Para procesar parcialmente, elimina del wizard las líneas que no se procesarán en ese momento.
