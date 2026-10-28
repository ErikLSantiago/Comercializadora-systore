# MKP Payment Gateway Commission 19.0

Versión técnica: `19.0.1.2.0`.

Este módulo agrega una configuración de comisiones por pasarela a las órdenes de venta y permite combinar varias pasarelas en una sola venta.

Al publicar una factura de cliente creada desde una orden de venta:

1. toma los importes capturados manualmente para Comisión Pasarela, Comisión Fija y sus IVA;
2. asigna cada importe a la cuenta configurada para ese concepto;
3. crea un asiento de gasto en el diario configurado; y
4. concilia la contrapartida contra la cuenta por cobrar de la factura.

Cada renglón de pago puede usar una pasarela y un importe diferente. La suma no puede superar el total de la orden. Las comisiones y sus IVA son de captura manual; el módulo no aplica porcentajes ni calcula automáticamente esos importes. Si las pasarelas usan diarios distintos, se crea un asiento por diario.

El módulo no depende de compras ni de `mkp_seller_dropship`, no crea facturas de proveedor y no utiliza campos de costo de venta.

## Configuración

En **Contabilidad > Configuración > Configuración de pasarelas > Pasarelas** configure:

- el contacto de la pasarela;
- la cuenta de Comisión Pasarela;
- la cuenta de Comisión Fija;
- la cuenta de IVA Comisión Pasarela;
- la cuenta de IVA Comisión Fija; y
- el diario general de comisiones.

Después agregue una línea por cada pago en la pestaña **Comisión de pasarela** de la orden de venta e indique manualmente el importe procesado, las comisiones y sus IVA.
