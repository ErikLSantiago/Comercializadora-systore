picking_email
=============

Módulo para Odoo v18 (Enterprise/SH) que agrega un botón **"Enviar por correo electrónico"**
en las operaciones de almacén (`stock.picking`), con soporte de **plantilla favorita**.

- Usa el asistente estándar de redacción de correo (edición previa al envío).
- Registra el mensaje en el **chatter** del picking.
- Una (1) plantilla favorita por modelo.

Nota: Se eliminó el valor dinámico del campo `lang` de la plantilla por cambios en v17+.