# Analítica de ventas — Odoo 18

Módulo analítico para consolidar Facturación, Ventas, Inventario por lote y Compras.

## Alcance productivo

- La factura es la autoridad para las piezas conciliadas.
- Distribuye las piezas facturadas entre movimientos/lotes de forma cronológica sin reutilizar cantidades asignadas a facturas anteriores.
- Relaciona lote + SKU con la orden de compra para obtener costo unitario y costo total.
- Calcula venta, costo, utilidad y margen.
- Clasifica canales de venta mediante configuración de cuentas contables.
- Marketplace/otros: una contrapartida `106.xx` de Tránsito genera una línea positiva de venta bruta y una línea negativa de devolución en tránsito.
- Mayoreo: los documentos `RINV` contabilizados en `402.01.10` se incorporan como devolución del canal Mayoreo. Los demás `RINV` se reservan para el futuro análisis de devoluciones efectivas.
- Identifica producto De línea / Open Box cuando existe `systore_is_open_box`.
- Tablero con KPIs, pasteles, composición de venta, cuadre y evolución.
- Segmentadores por periodo, estado, canal, cuenta, cliente, contacto, producto, proveedor y vendedor.

## Seguridad

- `Acceso a Analítica de ventas`: permite ver el módulo.
- `Administrador Analítica de ventas`: administración completa del módulo.
- Los usuarios limitados pueden restringirse por Canal, Cuenta contable y Vendedor.
- Las restricciones se aplican tanto al tablero como al Reporte consolidado mediante reglas de registros.
- `Ver reporte completo` elimina las restricciones para el usuario configurado.

## Configuración

**Analítica de ventas → Configuración** permite administrar:

1. Canales de venta y sus cuentas contables.
2. Permisos de usuarios internos.

## Actualización de datos

Después de cambios en reglas de negocio, lotes, órdenes de compra o campos de
producto, ejecutar **Actualizar reporte** para el periodo correspondiente. La
reconstrucción vuelve a consultar facturas, movimientos, lotes y compras; con
ello actualiza los costos automáticos y evita duplicar combinaciones ya
procesadas.

## Versión

18.0.1.4.3

## Costo manual de respaldo

Cuando una operación tiene Producto y Lote pero no existe una línea de Orden de compra que permita obtener el costo, un usuario del grupo **Administrador Analítica de ventas** puede editar **Costo unitario** desde el detalle del reporte. El valor se guarda como excepción por Compañía + Producto + Lote y se vuelve a aplicar automáticamente después de ejecutar **Actualizar reporte**. Un costo automático proveniente de OC no puede ser sobrescrito manualmente.
