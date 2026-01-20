# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class Certificate(models.Model):
    """Extend certificate types with Itaú API."""

    _inherit = "l10n_br_fiscal.certificate"

    type = fields.Selection(
        selection_add=[("itau_api", "API Itaú")],
        ondelete={"itau_api": "set default"},
    )
