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
    itau_nosso_numero = fields.Char(
        string="Nosso Número Itaú",
        copy=False,
        readonly=True,
    )
    itau_boleto_status = fields.Char(
        string="Status Boleto Itaú",
        copy=False,
        readonly=True,
    )
    itau_api_request = fields.Text(
        string="Itaú API Request",
        copy=False,
        readonly=True,
    )
    itau_api_response = fields.Text(
        string="Itaú API Response",
        copy=False,
        readonly=True,
    )
