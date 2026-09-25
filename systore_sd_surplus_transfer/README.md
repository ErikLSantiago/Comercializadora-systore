# Systore - Surplus Route (Odoo 18)

## Objetivo

Generalizar el flujo de excedentes para configurarlo directamente en **Inventario > Configuración > Rutas > Reglas**.

El módulo agrega una nueva acción a `stock.rule`:

**Surplus**

Cuando una llegada deja stock en la **Ubicación de origen** de la regla:

1. Odoo termina normalmente la operación que originó la llegada.
2. Odoo y el módulo reintentan las reservas de la demanda pendiente que consume esa ubicación.
3. Cualquier extensión del motor de reservas sigue funcionando. En particular, **Wholesale Allocation** conserva su filtro de lotes/OC porque Surplus llama al `_action_assign()` estándar.
4. El módulo compara el stock libre antes y después de la llegada.
5. Sólo la cantidad libre atribuible a esa llegada se envía a la **Ubicación de destino** usando el **Tipo de operación** de la regla.
6. En productos rastreados, la transferencia Surplus queda limitada al mismo lote/serie de la llegada.
7. La nueva transferencia queda creada y reservada, pero no validada.

## Configuración para San Diego -> Firme México

No es necesario borrar la ruta ni recrear la regla actual.

En la regla que hoy representa el tramo `SD/Existencias -> MX/Entrada` configure:

- **Acción:** `Surplus`
- **Tipo de operación:** la operación que deba generarse para Firme México (por ejemplo `Firme México: Recepciones` o el tipo operativo que corresponda)
- **Ubicación de origen:** `SD/Existencias`
- **Ubicación de destino:** `MX/Entrada`

La ruta puede seguir aplicándose por almacén, producto, categoría, embalaje o línea de venta según las herramientas nativas de Odoo.

### Importante sobre la regla Push anterior

La regla que debe hacer este mismo tramo no puede seguir con acción `Push` o `Pull y push` al mismo tiempo que se espera el comportamiento Surplus, porque la lógica nativa de Push puede mover la llegada completa antes de calcular el excedente.

No hace falta eliminar la regla: **se conserva la misma regla y se cambia únicamente su Acción a `Surplus`**.

Otras reglas de la ruta que cubran tramos distintos se mantienen sin cambios.

## Ejemplo

- Antes de recibir: stock libre en SD = 0.
- Llegan 100 unidades a `SD/Existencias`.
- Hay demanda pendiente por 20.
- Odoo/Wholesale Allocation reservan 20.
- Stock libre atribuible a la llegada = 80.
- La regla Surplus crea la operación configurada por 80 hacia `MX/Entrada`.

## Inventario previo

- Stock libre previo: 30.
- Nueva llegada: 100.
- Demanda pendiente: 20.
- Stock libre después de reservas: 110.
- Excedente atribuible a la llegada: `110 - 30 = 80`.
- Surplus transfiere 80, no 110.

## Compatibilidad con Wholesale Allocation

No existe una dependencia técnica obligatoria con `wholesale_allocation`.

Si Wholesale Allocation está instalado, su override de `_update_reserved_quantity()` continúa filtrando las reservas de ventas por los lotes/OC asociados. Surplus sólo observa el resultado de esas reservas y mueve el remanente.

Ejemplo:

- llega lote/PO `P02500`: 100;
- SO Wholesale asociada a `P02500`: 20;
- SO Wholesale asociada a `P02600`: 20;
- Wholesale reserva 20 de `P02500` para la primera SO;
- la segunda SO no puede tomar `P02500`;
- Surplus mueve 80 del lote `P02500`.

## Alcance genérico

Surplus no está limitado a recepciones de proveedor. Puede activarse después de cualquier movimiento de stock validado que llegue a la ubicación origen de una regla Surplus, por ejemplo:

- Proveedor -> Almacén A -> excedente a Almacén B.
- Entrada -> Stock -> excedente a otro centro.
- Almacén regional -> almacén central.
- Cadenas de excedente entre varios almacenes, configurando una regla Surplus en cada tramo.

Los ajustes de inventario y movimientos de devolución no disparan Surplus automáticamente.

## Aplicabilidad y dominio

La regla Surplus utiliza el mismo mecanismo de búsqueda de rutas que Odoo para localizar reglas por:

- rutas del movimiento;
- producto y categoría;
- embalaje;
- rutas del almacén;
- secuencia de ruta/regla.

También se puede utilizar **Aplicabilidad Push** (`push_domain`) para filtrar qué movimientos pueden activar la regla.

## Prevención de duplicados

Cada `stock.move` de llegada queda marcado como **Surplus procesado** una vez evaluado, incluso cuando no queda excedente. Esto evita que una cantidad liberada días después se confunda con el excedente de una recepción anterior.

## Actualización desde 18.0.1.0.0

La configuración anterior por almacén se conserva técnicamente para permitir la actualización del módulo, pero queda inactiva y ya no gobierna el proceso.

Después de actualizar:

1. Abra la ruta correspondiente.
2. Abra la regla del tramo que debe mover excedentes.
3. Cambie **Acción** a `Surplus`.
4. Revise Tipo de operación, Ubicación de origen y Ubicación de destino.
5. Pruebe primero en desarrollo.

## Pruebas recomendadas

### 1. Excedente simple
- Llegada: 100.
- Demanda pendiente en origen: 20.
- Esperado: 20 reservadas + Surplus 80.

### 2. Sin demanda
- Llegada: 100.
- Demanda: 0.
- Esperado: Surplus 100.

### 3. Demanda mayor a la llegada
- Llegada: 100.
- Demanda: 130.
- Esperado: 100 reservadas + ningún Surplus.

### 4. Inventario previo
- Libre previo: 30.
- Llegada: 100.
- Demanda: 20.
- Esperado: Surplus 80; no 110.

### 5. Wholesale Allocation
- `P02500`: llegada 100.
- SO asociada a `P02500`: 20.
- Otra SO asociada a `P02600`: 20.
- Esperado: reserva 20 de `P02500` y Surplus 80 de `P02500`.

### 6. Recepción parcial / backorder
- Primera llegada: 40, demanda 20 -> Surplus 20.
- Segunda llegada: 60, demanda 0 -> Surplus 60.

### 7. Varios productos / reglas
- Un mismo picking contiene productos cubiertos por reglas Surplus distintas.
- Esperado: una transferencia por regla aplicable con sus productos correspondientes.

## Versión

`18.0.1.1.0`
