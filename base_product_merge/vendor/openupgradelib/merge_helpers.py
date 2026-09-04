# Copyright Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging
from datetime import datetime

from odoo import release
from psycopg2 import IntegrityError, ProgrammingError

logger = logging.getLogger("ProductMerge")
version_info = release.version_info


def logged_query(cr, query, args=None, skip_no_result=False):
    """Execute a parametrized query and log its duration and affected rows."""
    args = () if args is None else args
    args = tuple(args) if isinstance(args, list) else args
    started = datetime.now()
    try:
        cr.execute(query, args)
    except (ProgrammingError, IntegrityError):
        logger.exception("Product merge SQL operation failed")
        raise
    if not skip_no_result or cr.rowcount:
        logger.debug(
            "%s rows affected by product merge in %s",
            cr.rowcount,
            datetime.now() - started,
        )
    return cr.rowcount


def table_exists(cr, table):
    cr.execute("SELECT 1 FROM pg_class WHERE relname = %s", (table,))
    return bool(cr.fetchone())


def column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM pg_attribute "
        "WHERE attrelid = (SELECT oid FROM pg_class WHERE relname = %s) "
        "AND attname = %s AND NOT attisdropped",
        (table, column),
    )
    return bool(cr.fetchone())


def get_model2table(model):
    special_tables = {
        "ir.actions.actions": "ir_actions",
        "ir.actions.act_window": "ir_act_window",
        "ir.actions.act_window.view": "ir_act_window_view",
        "ir.actions.act_window_close": "ir_actions",
        "ir.actions.act_url": "ir_act_url",
        "ir.actions.server": "ir_act_server",
        "ir.actions.client": "ir_act_client",
        "ir.actions.report": "ir_act_report_xml",
        "project.task.stage.personal": "project_task_user_rel",
    }
    return special_tables.get(model, model.replace(".", "_"))


def _module_installed(cr, module):
    cr.execute(
        "SELECT 1 FROM ir_module_module "
        "WHERE name = %s AND state IN ('installed', 'to upgrade')",
        (module,),
    )
    return bool(cr.fetchone())


def get_many2one_references(cr):
    references = [
        ("ir.model.data", "res_id", "model", ""),
        ("ir.attachment", "res_id", "res_model", ""),
    ]
    optional = {
        "mail": [
            ("mail.activity", "res_id", "res_model", "res_model_id"),
            ("mail.followers", "res_id", "res_model", ""),
            ("mail.message", "res_id", "model", ""),
            ("mail.scheduled.message", "res_id", "model", ""),
        ],
        "calendar": [("calendar.event", "res_id", "res_model", "res_model_id")],
        "rating": [
            ("rating.rating", "res_id", "res_model", "res_model_id"),
            (
                "rating.rating",
                "parent_res_id",
                "parent_res_model",
                "parent_res_model_id",
            ),
        ],
        "loyalty": [("loyalty.history", "order_id", "order_model", "")],
        "mass_mailing": [("mailing.trace", "res_id", "model", "")],
    }
    for module, module_references in optional.items():
        if _module_installed(cr, module):
            references.extend(module_references)
    return references
