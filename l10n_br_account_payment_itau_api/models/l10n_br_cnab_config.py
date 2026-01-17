# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class L10nBRCNABConfig(models.Model):
    """Extend CNAB config with Itaú API settings."""

    _inherit = "l10n_br_cnab.config"

    itau_certificate_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.certificate",
        string="Certificado Itaú",
    )
    itau_api_url = fields.Char(
        string="Itaú API URL",
        default="https://api.itau.com.br/cobranca/v2",
    )
    itau_client_id = fields.Char(
        string="Itaú Client ID",
    )
    itau_client_secret = fields.Char(
        string="Itaú Client Secret",
    )

    @api.model
    def _selection_cnab_processor(self):
        """Add Itaú API to the CNAB processor selection list."""
        _logger.info("Adding Itaú API to CNAB processor selection.")
        selection = super()._selection_cnab_processor()
        selection.append(("itau_api", "Itaú API"))
        return selection
