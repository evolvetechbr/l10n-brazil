# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    """Extend boleto print flow to support Itaú API using BRCobranca logic."""

    _inherit = "account.move"

    def generate_boleto_pdf(self):
        """Generate boleto PDF for Itaú API using the BRCobranca mechanism."""
        if self.payment_mode_id.cnab_config_id.cnab_processor != "itau_api":
            return super().generate_boleto_pdf()

        _logger.info("Generating boleto PDF via BRCobranca mechanism for Itaú API.")
        file_pdf = self.file_boleto_pdf_id
        if file_pdf:
            self.file_boleto_pdf_id = False
            file_pdf.unlink()

        receivable_ids = self.mapped("due_line_ids")
        boletos = receivable_ids.send_payment()
        if not boletos:
            raise UserError(
                _(
                    "It is not possible generated boletos\n"
                    "Make sure the Invoice are in Confirm state and "
                    "Payment Mode method are CNAB."
                )
            )

        pdf_string = self._get_brcobranca_boleto(boletos)

        inv_number = self.get_invoice_fiscal_number().split("/")[-1].zfill(8)
        file_name = "boleto_nf-" + inv_number + ".pdf"

        self.file_boleto_pdf_id = self.env["ir.attachment"].create(
            {
                "name": file_name,
                "store_fname": file_name,
                "res_model": self._name,
                "res_id": self.id,
                "datas": base64.b64encode(pdf_string),
                "mimetype": "application/pdf",
                "type": "binary",
            }
        )
