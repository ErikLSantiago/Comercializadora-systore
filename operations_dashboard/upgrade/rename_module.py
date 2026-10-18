"""Explicit pre-upgrade script; not imported or run by installing this addon."""
from odoo.upgrade import util


def migrate(cr, version):
    old = 'systore_operations_dashboard'
    new = 'operations_dashboard'
    cr.execute('SELECT name, state FROM ir_module_module WHERE name IN %s', ((old, new),))
    states = dict(cr.fetchall())
    if old not in states:
        if new in states:
            return
        raise RuntimeError('No se encontró el módulo de origen ni el destino.')
    if states[old] not in ('installed', 'to upgrade'):
        raise RuntimeError('El módulo de origen no está instalado; revise la base seleccionada.')
    if new in states:
        raise RuntimeError('El nombre de destino ya existe en la base. Revise el conflicto antes de migrar.')
    util.rename_module(cr, old, new)
