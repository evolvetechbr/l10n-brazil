# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountPaymentOrder(models.Model):
    """Extend payment order with generic boleto API emission hooks."""

    _inherit = "account.payment.order"

    cnab_processor = fields.Char(
        compute="_compute_cnab_processor",
        readonly=True,
        string="CNAB Processor",
    )

    def _compute_cnab_processor(self):
        for order in self:
            order.cnab_processor = (
                order.payment_mode_id.cnab_config_id.cnab_processor or False
            )

    def action_registrar_boleto(self):
        """Registra boletos for payment lines via a boleto API implementation.

        Raises:
            UserError: When validation fails or the API request errors.
        """
        _logger.info("Starting boleto API emission for %s.", self.display_name)
        self.ensure_one()

        cnab_config = self.cnab_config_id
        if not cnab_config:
            raise UserError(_("Missing CNAB configuration on the payment order."))
        if not self.payment_line_ids:
            raise UserError(_("There are no payment lines to process."))

        self._validate_boleto_api_order(cnab_config)
        client = self._get_boleto_api_client(  # pylint: disable=assignment-from-none
            cnab_config
        )
        if not client:
            raise UserError(_("No boleto API client configured for this processor."))

        for line in self.payment_line_ids:
            try:
                move = line.move_id or line.move_line_id.move_id
                if not move:
                    raise UserError(
                        _("Payment line %(line)s has no invoice.")
                        % {"line": line.display_name}
                    )
                if move.state != "posted":
                    raise UserError(
                        _("Invoice %(invoice)s must be confirmed before emission.")
                        % {"invoice": move.display_name}
                    )
                partner = line.partner_id or move.partner_id
                if not partner or not partner.cnpj_cpf:
                    raise UserError(
                        _("Partner CNPJ/CPF is required for %(partner)s.")
                        % {
                            "partner": partner.display_name
                            if partner
                            else line.display_name
                        }
                    )
                if not move.invoice_date_due:
                    raise UserError(
                        _("Invoice %(invoice)s has no due date.")
                        % {"invoice": move.display_name}
                    )

                payload = self._prepare_boleto_payload(  # pylint: disable=assignment-from-none
                    line,
                    move,
                    partner,
                    cnab_config,
                )
                if not payload:
                    raise UserError(
                        _("No boleto payload builder configured for this processor.")
                    )
                api_return = client.emitir_boleto(payload)
                response_payload = self._extract_response_payload(api_return)
                self.env[
                    "l10n_br_account_payment_boleto_api.event"
                ].create_event_save_json(
                    payment_line=line,
                    request_payload=payload,
                    response_payload=response_payload,
                )

                self._handle_boleto_response(line, api_return)
                self._post_boleto_message(partner, api_return)
            except UserError:
                raise
            except Exception as exc:
                _logger.exception(
                    "Error emitting boleto via API for payment line %s.",
                    line.display_name,
                )
                raise UserError(_("Error emitting boleto via API: %s") % exc) from exc

        return True

    def action_consultar_boleto(self):
        """Consult boletos using the configured boleto API implementation.

        Raises:
            UserError: When validation fails or the API request errors.
        """
        _logger.info("Starting boleto API consultation for %s.", self.display_name)
        self.ensure_one()

        cnab_config = self.cnab_config_id
        if not cnab_config:
            raise UserError(_("Missing CNAB configuration on the payment order."))
        if not self.payment_line_ids:
            raise UserError(_("There are no payment lines to process."))

        self._validate_boleto_api_order(cnab_config)
        client = self._get_boleto_api_client(  # pylint: disable=assignment-from-none
            cnab_config
        )
        if not client:
            raise UserError(_("No boleto API client configured for this processor."))

        for line in self.payment_line_ids:
            try:
                query_params = self._prepare_boleto_query_params(  # pylint: disable=assignment-from-none
                    line,
                    cnab_config,
                )
                if not query_params:
                    raise UserError(
                        _("No boleto consultation configured for this processor.")
                    )
                response_data = client.consultar_boleto(query_params)
                response_payload = self._extract_response_payload(response_data)
                self.env[
                    "l10n_br_account_payment_boleto_api.event"
                ].create_event_save_json(
                    payment_line=line,
                    request_payload=query_params,
                    response_payload=response_payload,
                    event_type="consultar_boleto",
                )

                self._handle_boleto_consulta_response(line, response_data)
                self._post_boleto_consulta_message(line, response_data)
            except UserError:
                raise
            except Exception as exc:
                _logger.exception(
                    "Error consulting boleto via API for payment line %s.",
                    line.display_name,
                )
                raise UserError(_("Error consulting boleto via API: %s") % exc) from exc

        return True

    def _validate_boleto_api_order(self, cnab_config):
        """Hook to validate boleto API settings before emission."""
        _logger.info("Validating boleto API configuration for %s.", cnab_config.name)

    def _get_boleto_api_client(self, cnab_config):
        """Return the API client implementation for the boleto processor."""
        return None

    def _prepare_boleto_payload(self, line, move, partner, cnab_config):
        """Prepare the boleto payload for the configured API."""
        return None

    def _handle_boleto_response(self, line, response_data):
        """Hook to persist response data on the payment line."""
        _logger.info(
            "Boleto API response received for payment line %s.", line.display_name
        )

    def _post_boleto_message(self, partner, response_data):
        """Hook to post a chatter message after successful emission."""
        _logger.info(
            "Posting boleto API emission message for %s.",
            partner.display_name,
        )

    def _extract_response_payload(self, response_data):
        """Extract JSON payload from response data for event logging."""
        if isinstance(response_data, dict):
            return response_data.get("response_data", {}) or {}
        raw = getattr(response_data, "return_msg_detail", None)
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _prepare_boleto_query_params(self, line, cnab_config):
        """Prepare query parameters for boleto consultation."""
        return None

    def _handle_boleto_consulta_response(self, line, response_data):
        """Hook to persist consultation response data on the payment line."""
        _logger.info(
            "Boleto API consultation response received for payment line %s.",
            line.display_name,
        )

    def _post_boleto_consulta_message(self, line, response_data):
        """Hook to post a chatter message after successful consultation."""
        _logger.info(
            "Posting boleto API consultation message for %s.",
            line.display_name,
        )
