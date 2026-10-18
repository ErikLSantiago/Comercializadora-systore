# Renombrar una instalación existente

Origen real de esta entrega: `systore_operations_dashboard`.
Destino: `operations_dashboard` · Odoo 18 · versión 18.0.1.7.2.

## Base nueva

Copie solamente la carpeta `operations_dashboard` en addons e instálela con las dependencias existentes. No cargue a la vez la carpeta anterior.

## Base con el addon anterior instalado

Cambiar una carpeta no cambia `ir.module.module` ni la propiedad de los identificadores XML. No desinstale el módulo: eso podría eliminar configuración y registros propios.

1. Trabaje primero sobre una copia de la base en una rama de pruebas.
2. Busque otros addons que dependan de `systore_operations_dashboard` o referencien sus identificadores XML/acciones/recursos. Actualice esas referencias a `operations_dashboard` en el mismo despliegue. Los nombres de modelos y campos no cambian.
3. Prepare el despliegue con la carpeta nueva reemplazando la anterior y una fase de **preactualización**, anterior a la carga del registro de módulos. Use la utilidad oficial `odoo.upgrade.util.rename_module(cr, old, new)` con los nombres anteriores. El archivo `upgrade/rename_module.py` implementa ese paso y detiene la ejecución si hay un conflicto de nombres. Requiere `odoo.upgrade.util` disponible en el entorno.
4. Configure ese archivo como script de preactualización en su procedimiento de despliegue Odoo 18; no es una migración automática del nuevo addon. Su administrador de Odoo.sh debe coordinar la ejecución y el cambio de código. No ejecute una instalación del nuevo módulo antes del renombrado.
5. Después del renombrado, actualice `operations_dashboard` con el código nuevo. Esto actualiza los valores de acciones cliente y las referencias de recursos. Reinicie y recargue el navegador.
6. Compruebe que solo aparece el addon nuevo como instalado, que se conservan almacenes/usuarios/cajas y que abren las seis pantallas. Pruebe los movimientos en la rama de pruebas antes de producción.

Si el destino ya aparece en Aplicaciones, el script exige revisar ese conflicto; no elimina ni fusiona registros silenciosamente. Si el nombre real en su base es `systore_operations_dasboard` (sin la h), se necesita ajustar el origen tras comprobarlo: no corresponde al código original de esta entrega.

Referencia oficial: https://www.odoo.com/documentation/18.0/developer/reference/upgrades/upgrade_utils.html

Verificación de esta entrega: referencias y sintaxis locales, plantillas Owl y carga de acciones. La migración de una base Odoo no se ejecutó en este entorno.
