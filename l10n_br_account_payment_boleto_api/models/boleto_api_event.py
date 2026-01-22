# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import json
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class BoletoAPIEvent(models.Model):
    """Event log for boleto API requests/responses with attachments."""

    _name = "l10n_br_account_payment_boleto_api.event"
    _description = "Boleto API Event"
    _order = "create_date desc, id desc"

    payment_line_id = fields.Many2one(
        comodel_name="account.payment.line",
        required=True,
        ondelete="cascade",
        index=True,
    )
    event_type = fields.Selection(
        selection=[("emitir_boleto", "Emitir Boleto")],
        required=True,
        default="emitir_boleto",
    )
    file_request_id = fields.Many2one(
        comodel_name="ir.attachment",
        string="Request File",
        readonly=True,
        copy=False,
    )
    file_response_id = fields.Many2one(
        comodel_name="ir.attachment",
        string="Response File",
        readonly=True,
        copy=False,
    )
    request_json_content = fields.Text(
        string="Request JSON",
        related="file_request_id.json_content",
        readonly=True,
    )
    response_json_content = fields.Text(
        string="Response JSON",
        related="file_response_id.json_content",
        readonly=True,
    )
    response_message = fields.Char(
        readonly=True,
    )

    def create_event_save_json(self, payment_line, request_payload, response_payload):
        """Create event and attach request/response payloads as JSON files."""
        _logger.info(
            "Creating boleto API event for payment line %s.",
            payment_line.name,
        )
        event = self.create({"payment_line_id": payment_line.id})

        request_name = f"boleto_api_request_{payment_line.id}.json"
        response_name = f"boleto_api_response_{payment_line.id}.json"

        request_json = json.dumps(request_payload, ensure_ascii=True, indent=2)
        response_json = json.dumps(response_payload, ensure_ascii=True, indent=2)

        request_attachment = self.env["ir.attachment"].create(
            {
                "name": request_name,
                "res_model": event._name,
                "res_id": event.id,
                "datas": base64.b64encode(request_json.encode("utf-8")),
                "mimetype": "application/json",
                "type": "binary",
            }
        )
        response_attachment = self.env["ir.attachment"].create(
            {
                "name": response_name,
                "res_model": event._name,
                "res_id": event.id,
                "datas": base64.b64encode(response_json.encode("utf-8")),
                "mimetype": "application/json",
                "type": "binary",
            }
        )

        event.write(
            {
                "file_request_id": request_attachment.id,
                "file_response_id": response_attachment.id,
            }
        )
        return event
