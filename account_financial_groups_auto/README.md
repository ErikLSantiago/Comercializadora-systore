# Financial Groups (Auto) - Odoo 18

Este módulo agrega:
- Grupos financieros (account.financial.group)
- Campo 'Grupo financiero' en cuentas contables (account.account.financial_group_id)
- Reglas de asignación automática (account.financial.group.rule)
- Wizard para recalcular grupos en lote

Uso:
1) Instala el módulo.
2) Crea tus grupos en Contabilidad > Configuración > Grupos financieros.
3) Crea reglas (prefijos de código, regex, contiene en nombre, tipo de cuenta).
4) Ejecuta "Recalcular grupos (por reglas)" para asignar.
5) (Opcional) Activa "Bloquear edición de grupo" en cuentas para evitar cambios manuales.

Nota: La agrupación en el P&L se configura desde el diseñador del reporte:
- En la línea EXP, usar Agrupar por: account_id.financial_group_id y luego una sub-línea con account_id.
