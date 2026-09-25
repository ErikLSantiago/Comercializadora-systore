from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.osv import expression


class StockRule(models.Model):
    _inherit = 'stock.rule'

    action = fields.Selection(
        selection_add=[('surplus', 'Surplus')],
        ondelete={'surplus': 'set default'},
    )

    def _get_message_dict(self):
        message_dict = super()._get_message_dict()
        source, destination, _direct_destination, operation = self._get_message_values()
        message_dict['surplus'] = _(
            'When products arrive in <b>%(source_location)s</b>, existing pending '
            'demand from that location is reserved first. The free quantity attributable '
            'to that arrival is then moved with <b>%(operation)s</b> to '
            '<b>%(destination)s</b>.',
            source_location=source,
            operation=operation,
            destination=destination,
        )
        return message_dict

    @api.constrains('action', 'location_src_id', 'location_dest_id', 'picking_type_id')
    def _check_surplus_configuration(self):
        for rule in self.filtered(lambda r: r.action == 'surplus'):
            if not rule.location_src_id:
                raise ValidationError(_('A Surplus rule requires a source location.'))
            if not rule.location_dest_id:
                raise ValidationError(_('A Surplus rule requires a destination location.'))
            if not rule.picking_type_id:
                raise ValidationError(_('A Surplus rule requires an operation type.'))
            if rule.location_src_id == rule.location_dest_id:
                raise ValidationError(_(
                    'The source and destination locations of a Surplus rule must be different.'
                ))


class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'

    @api.model
    def _get_rule_domain(self, locations, values):
        """Surplus is arrival-driven and must never be selected as a pull rule."""
        domain = super()._get_rule_domain(locations, values)
        return expression.AND([domain, [('action', '!=', 'surplus')]])

    @api.model
    def _get_surplus_rule(self, product_id, location_dest_id, values):
        """Find the Surplus rule that applies when stock arrives in a location.

        This mirrors Odoo's push-rule lookup, but keeps Surplus independent from
        native Push/Pull & Push rules. Route, product/category, packaging and
        warehouse applicability are therefore resolved by Odoo's normal rule
        search machinery.
        """
        found_rule = self.env['stock.rule']
        location = location_dest_id
        while (not found_rule) and location:
            domain = [('location_src_id', '=', location.id), ('action', '=', 'surplus')]
            if values.get('domain'):
                domain = expression.AND([domain, values['domain']])
            found_rule = self._search_rule(
                values.get('route_ids'),
                values.get('product_packaging_id'),
                product_id,
                values.get('warehouse_id'),
                domain,
            )
            location = location.location_id
        return found_rule
