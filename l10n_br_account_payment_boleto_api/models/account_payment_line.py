# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountPaymentLine(models.Model):
    """Store Itaú boleto metadata on payment lines."""

    _inherit = "account.payment.line"

    cnab_state = fields.Selection(
        related="move_line_id.cnab_state",
        string="CNAB Status",
        readonly=True,
    )
    payment_situation = fields.Selection(
        related="move_line_id.payment_situation",
        string="Situação do Pagamento",
        readonly=True,
    )
    nosso_numero = fields.Char(
        string="Nosso Número",
        copy=False,
        readonly=True,
    )
    boleto_status = fields.Char(
        string="Status Boleto",
        copy=False,
        readonly=True,
    )
    boleto_api_event_ids = fields.One2many(
        comodel_name="l10n_br_account_payment_boleto_api.event",
        inverse_name="payment_line_id",
        string="Boleto API Events",
        readonly=True,
    )
