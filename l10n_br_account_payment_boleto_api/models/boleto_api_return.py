# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class BoletoAPIReturn(models.Model):
    """Store API return details for boleto registration."""

    _name = "l10n_br_account_payment_boleto_api.return"
    _description = "Boleto API Return"

    return_code = fields.Char(
        readonly=True,
    )
    success = fields.Boolean(
        readonly=True,
    )
    return_msg_detail = fields.Text(
        string="Return Message Detail",
        readonly=True,
    )
    return_msg = fields.Char(
        string="Return Message",
        readonly=True,
    )
    beneficiaryid = fields.Char(
        string="Beneficiary ID",
        readonly=True,
    )
    boletoid = fields.Char(
        string="Boleto ID",
        readonly=True,
    )
    barcode_typed = fields.Char(
        readonly=True,
    )
    barcode = fields.Char(
        readonly=True,
    )
