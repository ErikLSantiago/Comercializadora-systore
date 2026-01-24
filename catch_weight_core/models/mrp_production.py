from odoo import models, _
from odoo.exceptions import UserError

class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def button_mark_done(self):
        # Interceptar el cierre para productos catch-weight y abrir wizard
        self.ensure_one()
        if self.product_id.product_tmpl_id.x_is_catch_weight and not self.env.context.get("cw_from_wizard"):
            return {
                "type": "ir.actions.act_window",
                "name": _("Finalizar producción (Catch Weight)"),
                "res_model": "mrp.cw.finish.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_production_id": self.id,
                    "default_production_date": self.env["fields.datetime"].now(),
                },
            }
        return super().button_mark_done()
