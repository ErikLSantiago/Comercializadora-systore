Operaciones: Enviar por correo (Stock Picking)
=============================================

Este módulo para Odoo v18 (Enterprise/SH) agrega un botón **"Enviar por correo electrónico"**
en las operaciones de almacén (`stock.picking`).

Características
---------------
- Abre el asistente estándar de **Redactar correo** (`mail.compose.message`) con la plantilla favorita.
- Permite **editar** el contenido antes de enviar.
- Puedes marcar una plantilla como **favorita** para `stock.picking` (una por modelo y compañía).
- El mensaje queda **registrado en el chatter** de la operación (histórico de comunicación/seguimientos).

Configuración
-------------
1. Ve a **Inventario → Configuración → Plantillas de correo**.
2. Crea/edita una plantilla para el modelo `stock.picking` y marca el checkbox **Favorita (para este modelo)**.
3. Desde una operación de almacén con **Cliente** asignado, usa el botón **Enviar por correo electrónico**.

Notas
-----
- El botón se oculta si el picking no tiene `partner_id` o está `cancel`.
- La plantilla de ejemplo incluida se instala como favorita por defecto y puede modificarse.