import logging

from lxml import etree

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)


def _payment_field_nodes(root, view_model):
    """Return field nodes that are evaluated against systore.purchase.payment."""
    if view_model == "systore.purchase.payment":
        return root.xpath(".//field[@name]")

    nodes = []
    for payment_field in root.xpath(".//field[@name='systore_payment_line_ids']"):
        nodes.extend(payment_field.xpath(".//field[@name]"))
    for instruction in root.xpath(
        ".//xpath[contains(@expr, 'systore_payment_line_ids')]"
    ):
        nodes.extend(instruction.xpath(".//field[@name]"))
    return nodes


def _clean_arch(arch, view_model, valid_fields):
    root = etree.fromstring(arch.encode("utf-8"))
    removed = []
    for node in _payment_field_nodes(root, view_model):
        field_name = node.get("name")
        if field_name in valid_fields or node.getparent() is None:
            continue
        node.getparent().remove(node)
        removed.append(field_name)
    return etree.tostring(root, encoding="unicode"), removed


def migrate(cr, version):
    """Repair obsolete payment views without touching valid customizations."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    valid_fields = set(env["systore.purchase.payment"]._fields)
    View = env["ir.ui.view"].with_context(active_test=False)
    views = View.search([
        ("active", "=", True),
        ("model", "=", "systore.purchase.payment"),
    ])
    views |= View.search([
        ("active", "=", True),
        ("model", "=", "purchase.order"),
        ("arch_db", "ilike", "systore_payment_line_ids"),
    ])

    for view in views:
        arch = str(view.arch_db or "")
        if not arch:
            continue
        try:
            clean_arch, removed = _clean_arch(arch, view.model, valid_fields)
        except (etree.XMLSyntaxError, ValueError):
            _logger.warning("No fue posible analizar la vista de pagos %s", view.display_name)
            continue
        if not removed:
            continue
        try:
            with cr.savepoint():
                view.write({"arch_db": clean_arch})
        except Exception:
            _logger.exception(
                "No fue posible reparar la vista inválida %s; se desactivará.",
                view.display_name,
            )
            with cr.savepoint():
                view.write({"active": False})
        else:
            _logger.info(
                "Vista de pagos %s reparada; campos retirados: %s",
                view.display_name,
                ", ".join(sorted(set(removed))),
            )
