picking_email
=============

Módulo para Odoo v18 (Enterprise/SH) que agrega un botón **"Enviar por correo electrónico"**
en las operaciones de almacén (`stock.picking`), con soporte de **plantilla favorita**.

- Usa el asistente estándar de redacción de correo (edición previa al envío).
- Registra el mensaje en el **chatter** del picking.
- Una (1) plantilla favorita por modelo.

Hardening: si la plantilla favorita tiene un idioma inválido, el asistente abre sin plantilla para evitar errores.