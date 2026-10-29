# Cobranza MKP — v18.0.1.0.4 (prototipo manual)

Módulo independiente para **Odoo 18 Enterprise / Odoo.sh**.
No requiere Producteca, Odoo Studio ni módulos de comisiones como dependencias; se conecta con `sale.order`.

## Instalación

1. Hacer respaldo o duplicar **primero** la base a staging de Odoo.sh.
2. Subir la carpeta `mkp_collection_control` completa al repositorio de addons personalizados. Si se dispone de instalador ZIP en el entorno, comprobar antes el método de incorporación usado en esa instancia.
3. Actualizar la lista de Aplicaciones, buscar **Cobranza MKP** e instalar.
4. En Ajustes > Usuarios asignar **Cobranza MKP / Operador** o **Cobranza MKP / Supervisor**.
5. El usuario debe **tener ya permiso para consultar las órdenes de Ventas**. El módulo no concede acceso general a Ventas.
6. Usar **Ventas > Orden de venta > Cobranza** o el menú **Cobranza MKP**. El icono general abre directamente el historial de movimientos.

## Captura manual

- Elegir cualquier orden existente, incluidas las históricas. **Marketplace** se obtiene de `x_studio_canal_de_venta_1` y **Número de orden MKP** de `x_studio_nmero_de_orden_mkp`.
- El asistente trabaja con cuatro estados principales: **Borrador**, **Confirmado**, **Recalculado** y **Devolución**. Los subestados se incorporarán en una iteración posterior.
- Borrador, Confirmado y Recalculado guardan una fotografía completa del desglose: venta, Cupon, Killer, retenciones, comisión, comisión killer, comisión cupón, envío y otras comisiones. **Total de venta** calcula Venta − Cupon + Killer; **Monto a cobrar** usa ese nuevo total como base y descuenta las comisiones y cargos. Cada nueva fotografía registra solo la variación contra el saldo anterior.
- La sección **Cobranza** admite Importe, Referencia de pago, Fecha y Estado: Retenido, Pendiente, Pagado, Cancelado o Reembolso.
- Al volver a abrir el wizard se cargan los registros vigentes. Cambiar importe, referencia, fecha o estado crea una nueva revisión; la anterior permanece como Histórica. Eliminar una línea vigente desde el wizard genera una revisión Cancelada.
- Devolución registra el importe y el saldo de origen. No genera recepción, nota de crédito ni efecto contable.
- **Revertir**: exclusivo Supervisor; crea evento inverso con motivo. Si eventos posteriores consumieron fondos, se debe revertirlos primero para conservar la consistencia del saldo.

## Importación

El historial completo incluye la acción **Importar registros**. Abre un modelo de importación que usa el mapeo de columnas nativo de Odoo. Las columnas disponibles incluyen el desglose, la devolución y una cobranza por fila. Si la referencia coincide con un registro activo de la orden, la fila crea una revisión en lugar de duplicarlo.

## Orden e historial

- Expediente único por `sale.order`.
- Cuatro indicadores solicitados: `Retenido`, `Monto por cobrar`, `Liberado`, `Devoluciones` (esta última con signo negativo para mostrar la pérdida de cobranza).
- Indicador auxiliar: **Pagado informado**. Es una declaración manual de la liquidación del marketplace, *no conciliación bancaria*.
- Cada movimiento usa secuencia `COB/año/000001`, `Fecha del evento` (de la plataforma), `Fecha de captura` (automática), `Registrado por`, Estado, referencia, comentario y evidencia opcional.
- En el reporte general, únicamente el movimiento más reciente de cada expediente aparece con estatus **Activo**; los anteriores se conservan como **Histórico**.
- El reporte **Historial de registros de cobranza** muestra todas las revisiones, su referencia, fecha, importe, estado y estatus Activo/Histórico.
- Cada evento almacena **deltas** y fotografías de los saldos antes y después. El historial no permite editar/borrar eventos con ORM ordinario. Los saldos actuales solo se modifican desde el método interno de publicación del evento.
- Un movimiento con `Fecha del evento` anterior a su carga queda con **fotografía a la fecha en que se registró**, no una reescritura retrospectiva de cada saldo anterior. Por eso se conservan ambas fechas.

## Cálculos y ejemplo

Ejemplo Walmart del archivo de prueba:

- Venta inicial: MXN 5,499.00
- Retenciones: MXN 497.75, comisión MXN 549.90, envío MXN 100.00
- Neto inicial: **MXN 4,351.35**
- Una captura Recalculada puede sustituir el desglose completo y separar Comisión killer y Comisión cupón; el historial conserva únicamente las diferencias contra la fotografía anterior.
- Una devolución reduce el saldo indicado y acumula su impacto negativo en Devoluciones.
- Guía de MXN 100.00, **solo una vez en Otras comisiones**: resultado neto **−100.00**, representado como monto por cobrar negativo.

Si el dinero está repartido entre `Retenido`, `Liberado`, `Pagado reportado` y `Por cobrar`, la devolución debe registrarse en tantos eventos de origen como sean necesarios; no se permite descontar fondos inexistentes. La logística de devoluciones queda para la etapa posterior.

**Identidad invariante:**

`Venta - Cupon + Killer - retenciones - comisión - comisión killer - comisión cupón - envío - otras comisiones - devoluciones = monto por cobrar + retenido + liberado + pagado reportado`.

## Delimitación de la versión

No se incluyen CSV de importación, integración API, automatización de Producteca, validación de depósitos bancarios, conciliación, ajustes a facturas, asientos, IVA contable, P&L, movimientos de inventario, rutas logísticas ni tratamiento especial de devoluciones.

**IMPORTANTE:** Esta compilación pasa análisis estático Python/XML y pruebas unitarias de la lógica de cálculo en un entorno sin Odoo instalado. No se ha probado todavía el ciclo real de instalación y vistas sobre una base de Odoo.sh v18. Instalar en staging primero y compartir cualquier traceback para ajustes.
