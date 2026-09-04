# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class MarketplaceBillingConfig(models.Model):
    _name = "marketplace.billing.config"
    _description = "Marketplace Billing Configuration"
    _rec_name = "display_name"
    _order = "company_id, channel_binding_id"

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    # Producteca
    channel_binding_id = fields.Many2one(
        "producteca.channel.binding",
        string="Marketplace (Producteca Channel)",
        required=True,
        index=True,
        ondelete="restrict",
        help="Canal/Marketplace definido en Producteca (producteca.channel.binding).",
    )
    channel_id = fields.Many2one(
        "producteca.channel",
        string="Canal (Producteca)",
        related="channel_binding_id.channel_id",
        store=False,
        readonly=True,
    )
    code = fields.Char(string="Código", related="channel_binding_id.code", store=False, readonly=True)

    invoice_partner_id = fields.Many2one(
        "res.partner",
        string="Contacto para facturación",
        help="Se asigna en la orden de venta como Dirección de factura (partner_invoice_id).",
    )
    income_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de ingresos",
        domain=[("account_type", "=", "income")],
        help="Se fuerza en las líneas de factura generadas desde la venta.",
    )

    active = fields.Boolean(default=True)

    display_name = fields.Char(compute="_compute_display_name", store=False)

    @api.depends("company_id", "channel_binding_id")
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.company_id:
                parts.append(rec.company_id.name)
            if rec.channel_binding_id:
                parts.append(rec.channel_binding_id.display_name or rec.channel_binding_id.name)
            rec.display_name = " / ".join([p for p in parts if p]) or _("Configuración Marketplace")

    _sql_constraints = [
        ("uniq_company_channel_binding",
         "unique(company_id, channel_binding_id)",
         "Ya existe una configuración para este Marketplace en esta compañía."),
    ]
    @api.constrains("invoice_partner_id", "company_id")
    def _check_invoice_partner_company(self):
        for rec in self:
            if rec.invoice_partner_id and rec.invoice_partner_id.company_id and rec.company_id and rec.invoice_partner_id.company_id != rec.company_id:
                raise ValidationError(_(
                    "El contacto para facturación debe ser compartido (sin compañía) "
                    "o pertenecer a la misma compañía de la configuración."
                ))
