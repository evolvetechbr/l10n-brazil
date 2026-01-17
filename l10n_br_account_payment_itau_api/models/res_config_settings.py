# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Itaú API settings stored in system parameters."""

    _inherit = "res.config.settings"

    itau_api_url = fields.Char(
        string="Itaú API URL",
        config_parameter="l10n_br_account_payment_itau_api.itau_api_url",
        default="https://api.itau.com.br/cobranca/v2",
    )
    itau_client_id = fields.Char(
        string="Itaú Client ID",
        config_parameter="l10n_br_account_payment_itau_api.itau_client_id",
    )
    itau_client_secret = fields.Char(
        string="Itaú Client Secret",
        config_parameter="l10n_br_account_payment_itau_api.itau_client_secret",
    )
    itau_certificate_id = fields.Many2one(
        string="Certificado Itaú",
        comodel_name="l10n_br_fiscal.certificate",
        config_parameter="l10n_br_account_payment_itau_api.itau_certificate_id",
    )
