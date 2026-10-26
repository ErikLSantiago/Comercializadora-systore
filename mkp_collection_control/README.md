# Cobranza MKP — v18.0.1.0.0 (prototipo manual)

Módulo independiente para **Odoo 18 Enterprise / Odoo.sh**.
No requiere Producteca, Odoo Studio ni módulos de comisiones como dependencias; se conecta con `sale.order`.

## Instalación

1. Hacer respaldo o duplicar **primero** la base a staging de Odoo.sh.
2. Subir la carpeta `mkp_collection_control` completa al repositorio de addons personalizados. Si se dispone de instalador ZIP en el entorno, comprobar antes el método de incorporación usado en esa instancia.
3. Actualizar la lista de Aplicaciones, buscar **Cobranza MKP** e instalar.
4. En Ajustes > Usuarios asignar **Cobranza MKP / Operador** o **Cobranza MKP / Supervisor**.
5. El usuario debe **tener ya permiso para consultar las órdenes de Ventas**. El módulo no concede acceso general a Ventas.
6. Usar **Ventas > Orden de venta > Cobranza** o el menú **Cobranza MKP**.

## Captura manual

- **Desglose inicial**: elegir cualquier orden existente (incluye órdenes históricas), el nombre del marketplace, referencia de Producteca/MKP y registrar comisión, retenciones/impuestos, envío, otras comisiones. El formulario propone como venta inicial el `amount_total` de la orden, editable antes de confirmar el evento inicial. No se crea nada contable.
- **Reconocer retenido**: mueve dinero desde `Monto por cobrar` a `Retenido`.
- **Liberar**: mueve `Retenido` a `Liberado`. Existe alternativa de `Liberado directo`, desde `Por cobrar`.
- **Pago informado por MKP**: mueve `Liberado` a `Pagado reportado`, **sin crear pago ni acreditar depósito bancario**.
- **Cupón / killer**: incrementa la venta reportada y captura al mismo tiempo su comisión adicional. El diferencial se suma a `Por cobrar`.
- **Comisión, impuestos, envío y otras comisiones**: ajustan los importes de la venta reportada. Los cargos por guía se registran **una sola vez** como `Otras comisiones`. Se admiten ajustes negativos para corregir a la baja un cargo (siempre que las cifras totales permanezcan válidas).
- **Devolución financiera básica**: reduce el saldo indicado (pendiente, retenido, liberado o pagado reportado) y acumula su impacto negativo en `Devoluciones`. NO genera recepción ni nota de crédito.
- **Revertir**: exclusivo Supervisor; crea evento inverso con motivo. Si eventos posteriores consumieron fondos, se debe revertirlos primero para conservar la consistencia del saldo.

## Orden e historial

- Expediente único por `sale.order`.
- Cuatro indicadores solicitados: `Retenido`, `Monto por cobrar`, `Liberado`, `Devoluciones` (esta última con signo negativo para mostrar la pérdida de cobranza).
- Indicador auxiliar: **Pagado informado**. Es una declaración manual de la liquidación del marketplace, *no conciliación bancaria*.
- Cada movimiento usa secuencia `COB/año/000001`, `Fecha del evento` (de la plataforma), `Fecha de captura` (automática), `Registrado por`, `Qué pasó`, referencia y evidencia opcional.
- Cada evento almacena **deltas** y fotografías de los saldos antes y después. El historial no permite editar/borrar eventos con ORM ordinario. Los saldos actuales solo se modifican desde el método interno de publicación del evento.
- Un movimiento con `Fecha del evento` anterior a su carga queda con **fotografía a la fecha en que se registró**, no una reescritura retrospectiva de cada saldo anterior. Por eso se conservan ambas fechas.

## Cálculos y ejemplo

Ejemplo Walmart del archivo de prueba:

- Venta inicial: MXN 5,499.00
- Retenciones: MXN 497.75, comisión MXN 549.90, envío MXN 100.00
- Neto inicial: **MXN 4,351.35**
- Cupón +500.00 con comisión adicional +50.00 => +450.00 netos
- Killer +1,000.00 con comisión adicional +100.00 => +900.00 netos
- Neto ajustado **MXN 5,701.35**.
- Devolución completa por MXN 5,701.35 desde el saldo correspondiente: impacto de devoluciones **−5,701.35**.
- Guía de MXN 100.00, **solo una vez en Otras comisiones**: resultado neto **−100.00**, representado como monto por cobrar negativo.

Si el dinero está repartido entre `Retenido`, `Liberado`, `Pagado reportado` y `Por cobrar`, la devolución debe registrarse en tantos eventos de origen como sean necesarios; no se permite descontar fondos inexistentes. La logística de devoluciones queda para la etapa posterior.

**Identidad invariante:**

`Venta ajustada - retenciones - comisión - envío - otras comisiones - devoluciones = monto por cobrar + retenido + liberado + pagado reportado`.

## Delimitación de la versión

No se incluyen CSV de importación, integración API, automatización de Producteca, validación de depósitos bancarios, conciliación, ajustes a facturas, asientos, IVA contable, P&L, movimientos de inventario, rutas logísticas ni tratamiento especial de devoluciones.

**IMPORTANTE:** Esta compilación pasa análisis estático Python/XML y pruebas unitarias de la lógica de cálculo en un entorno sin Odoo instalado. No se ha probado todavía el ciclo real de instalación y vistas sobre una base de Odoo.sh v18. Instalar en staging primero y compartir cualquier traceback para ajustes.
