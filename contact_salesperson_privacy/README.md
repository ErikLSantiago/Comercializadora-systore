# Privacidad de contactos por vendedor — Odoo 18

Restringe contactos privados para que cada vendedor consulte solamente los que tiene asignados.

## Configuración

1. Instale el módulo `Contact Privacy by Salesperson`.
2. En **Ajustes → Usuarios y compañías → Usuarios**, abra cada usuario.
3. En **Privacidad de contactos**, seleccione:
   - **Restringido: solo contactos asignados** para vendedores.
   - **Alfa: todos los contactos** para administradores y personal de compras/contactos.
4. En **Contactos → Privacidad de contactos**, asigne un **Vendedor responsable** o agregue **Usuarios autorizados**.

## Comportamiento

- Un usuario restringido comienza sin acceso a la base de contactos y solo ve contactos asignados.
- Si un vendedor restringido crea un contacto, queda automáticamente como responsable y usuario autorizado.
- Los vendedores restringidos no pueden abrir por URL un contacto privado no autorizado.
- Al crear, guardar, reasignar o confirmar una orden de venta, su vendedor queda como responsable y autorizado en el cliente, empresa principal y direcciones de facturación/entrega.
- El acceso histórico se conserva aunque posteriormente cambie el vendedor de una orden.
- Si varios vendedores usan el mismo contacto, el último será el responsable principal y los anteriores permanecerán autorizados.
- Durante la instalación se sincronizan las órdenes de venta existentes.

## Prueba recomendada

1. Cree dos vendedores restringidos: Vendedor A y Vendedor B.
2. Cree dos contactos y asigne uno a cada vendedor.
3. Verifique desde Contactos, búsquedas y URL directa que no puedan consultar el contacto ajeno.
4. Cree una orden para el contacto B asignada al Vendedor A y confirme que ahora pueda consultarlo.
5. Compruebe que el usuario Alfa conserve acceso completo.

## Nota técnica

La protección usa una regla de registro sobre `res.partner`; no es un filtro visual. Antes de producción debe probarse con los módulos personalizados que consulten contactos mediante el usuario actual.
