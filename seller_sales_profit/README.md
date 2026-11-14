# Utilidad por ventas de sellers

Módulo para Odoo 18. Agrega el tablero **Comisiones por ventas seller** en **Contabilidad → Reportes** para usuarios con acceso de lectura contable.

## Instalación

El entorno debe admitir módulos Python personalizados, como Odoo.sh o un servidor propio.

1. Copia la carpeta `seller_sales_profit` al directorio de módulos personalizados. En Odoo.sh, incluye la carpeta en el repositorio y despliega primero en una rama de pruebas.
2. En Odoo, activa el modo de desarrollador y selecciona **Aplicaciones → Actualizar lista de aplicaciones**.
3. Busca **Utilidad por ventas de sellers** e instálalo. Retira el filtro predeterminado **Aplicaciones** si el módulo no aparece.

Si instalaste una versión anterior, reemplaza la carpeta del módulo y usa **Actualizar** en la ficha del módulo en Aplicaciones.

## Consulta

1. Abre la ficha del contacto, marca **Seller** y guarda. El selector del tablero muestra los contactos marcados. Las instalaciones existentes deben marcar sus sellers.
2. En el tablero, selecciona el seller y usa **Año** y **Mes** para definir el periodo por fecha contable. Elige **Todo el año** o ajusta **Desde** y **Hasta** para un rango personalizado.
3. Elige las cuentas por nombre. Ventas lista cuentas de tipo **Ingresos** y costo lista cuentas de tipo **Costo de ingresos**. El tablero preselecciona 401.01.01 para ventas y 501.01.01 para costo si existen en la compañía activa con el tipo correspondiente.
4. Pulsa **Consultar**. Usa **Ver apuntes** para revisar los movimientos incluidos en cada importe.

El tablero usa la compañía activa y su moneda contable. Agrupa por contacto comercial, incluyendo los contactos secundarios de la misma empresa. Si administras varios sellers bajo un mismo contacto comercial, este tablero los tratará como un solo seller.

Las tarjetas muestran **Ventas del seller**, **Total pagado al seller** y **Comisiones por ventas seller**. La gráfica divide el total de ventas entre costo y utilidad cuando ambos importes son positivos o cero y las ventas son mayores que cero. El cálculo incluye apuntes de la cuenta seleccionada en facturas y notas de crédito contabilizadas. Excluye IVA y toma el saldo contable en moneda de la compañía. Una nota de crédito reduce el importe de su lado. Las facturas pendientes de pago cuentan en el periodo.

Si para el mismo seller y periodo usas esas cuentas también para operaciones ajenas al portal, la consulta incluirá esas operaciones. En ese caso, usa cuentas dedicadas al portal o agrega un criterio de identificación antes de utilizar el tablero para medir exclusivamente el ecommerce.

## Validación en una base de prueba

Para un seller y un periodo, registra una factura de cliente por 1,000, una factura de proveedor por 800, una nota de crédito de cliente por 100 y una nota de crédito de proveedor por 50. Usa importes antes de IVA y los códigos configurados. Si son los únicos documentos aplicables, verifica que el tablero muestre 900 de ventas, 750 de costo y 150 de utilidad. Revisa los apuntes de cada tarjeta y confirma que un borrador, otra compañía y otro seller no alteren el resultado.
