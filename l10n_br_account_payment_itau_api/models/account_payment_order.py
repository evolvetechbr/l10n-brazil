# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from erpbrasil.base import misc

from odoo import _, fields, models
from odoo.exceptions import UserError

from .itau_api_client import ItauAPIClient

_logger = logging.getLogger(__name__)


class AccountPaymentOrder(models.Model):
    """Extend payment order with Itaú boleto emission action."""

    _inherit = "account.payment.order"

    cnab_processor = fields.Selection(
        selection=lambda self: self.env["l10n_br_cnab.config"]
        ._fields["cnab_processor"]
        .selection,
        compute="_compute_cnab_processor",
        readonly=True,
        string="CNAB Processor",
    )

    def _compute_cnab_processor(self):
        for order in self:
            order.cnab_processor = (
                order.payment_mode_id.cnab_config_id.cnab_processor or False
            )

    def action_emitir_boleto_itau(self):
        """Emit Itaú boletos for payment lines via Itaú API.

        Raises:
            UserError: When validation fails or the API request errors.
        """
        _logger.info("Starting Itaú boleto emission for %s.", self.display_name)
        self.ensure_one()

        cnab_config = self.cnab_config_id
        if not cnab_config:
            raise UserError(_("Missing CNAB configuration on the payment order."))
        if cnab_config.cnab_processor != "itau_api":
            raise UserError(_("CNAB processor is not configured for Itaú API."))
        if not cnab_config.itau_api_url:
            raise UserError(_("Itaú API URL is not configured."))
        if not self.payment_line_ids:
            raise UserError(_("There are no payment lines to process."))

        client = ItauAPIClient(cnab_config)

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

                payload = self._prepare_itau_boleto_payload(
                    line, move, partner, cnab_config
                )
                response_data = client.emitir_boleto(payload)

                line.write(
                    {
                        "itau_nosso_numero": response_data.get("nosso_numero"),
                        "itau_boleto_status": response_data.get("status") or "emitido",
                    }
                )
                self.message_post(
                    body=_(
                        "Boleto Itaú emitted for %(partner)s. "
                        "Nosso número: %(nosso)s. URL: %(url)s"
                    )
                    % {
                        "partner": partner.display_name,
                        "nosso": response_data.get("nosso_numero") or "-",
                        "url": response_data.get("url_boleto") or "-",
                    }
                )
            except UserError:
                raise
            except Exception as exc:
                _logger.exception(
                    "Error emitting Itaú boleto for payment line %s.",
                    line.display_name,
                )
                raise UserError(_("Error emitting Itaú boleto: %s") % exc) from exc

        return True

    def _prepare_itau_boleto_payload(self, line, move, partner, cnab_config):
        """Prepare Itaú boleto payload from payment line data.

        Args:
            line (account.payment.line): Payment line to emit.
            move (account.move): Invoice move linked to the payment line.
            partner (res.partner): Partner used as the boleto payer.
            cnab_config (l10n_br_cnab.config): CNAB configuration for Itaú.

        Returns:
            dict: Payload ready to be sent to Itaú API.
        """
        _logger.info("Preparing Itaú boleto payload for invoice %s.", move.display_name)
        company_partner = self.company_id.partner_id
        amount = line.amount_currency or move.amount_total
        due_date = move.invoice_date_due.isoformat()
        issue_date = (
            move.invoice_date or move.date or fields.Date.context_today(self)
        ).isoformat()

        payload = {
            "etapa_processo_boleto": "validacao",
            "codigo_canal_operacao": "API",
            "beneficiario": {
                "id_beneficiario": cnab_config.cnab_company_bank_code
                or cnab_config.convention_code
                or misc.punctuation_rm(company_partner.cnpj_cpf or ""),
                "nome_cobranca": self.company_id.name or company_partner.name,
                "tipo_pessoa": self._get_person_type_payload(company_partner),
                "endereco": self._get_address_payload(company_partner),
            },
            "dado_boleto": {
                "descricao_instrumento_cobranca": "boleto",
                "tipo_boleto": "a vista",
                "forma_envio": "impressão",
                "pagador": {
                    "pessoa": {
                        "nome_pessoa": partner.name or "",
                        "nome_fantasia": partner.name or "",
                        "tipo_pessoa": self._get_person_type_payload(partner),
                    },
                    "endereco": self._get_address_payload(partner),
                    "texto_endereco_email": partner.email or "",
                },
                "codigo_carteira": cnab_config.boleto_wallet or "",
                "codigo_tipo_vencimento": 1,
                "dados_individuais_boleto": [
                    {
                        "numero_nosso_numero": line.own_number or "",
                        "data_vencimento": due_date,
                        "valor_titulo": self._format_amount(amount),
                        "texto_seu_numero": line.document_number or move.name or "",
                        "data_limite_pagamento": due_date,
                        "texto_uso_beneficiario": line.company_title_identification
                        or move.ref
                        or "",
                    }
                ],
                "codigo_especie": cnab_config.boleto_species or "",
                "descricao_especie": self._get_selection_label(
                    cnab_config, "boleto_species"
                ),
                "codigo_aceite": cnab_config.boleto_accept or "",
                "data_emissao": issue_date,
                "pagamento_parcial": False,
                "texto_uso_beneficiario": line.company_title_identification
                or move.ref
                or "",
            },
        }

        if line.rebate_value:
            payload["dado_boleto"]["valor_abatimento"] = self._format_amount(
                line.rebate_value
            )
        if line.discount_value:
            payload["dado_boleto"]["desconto"] = {
                "codigo_tipo_desconto": (
                    cnab_config.boleto_discount_code_id.code
                    if cnab_config.boleto_discount_code_id
                    else "01"
                ),
                "descontos": [
                    {
                        "data_desconto": due_date,
                        "valor_desconto": self._format_amount(line.discount_value),
                    }
                ],
            }
        if line.percent_interest or line.interest_value or line.amount_interest:
            payload["dado_boleto"]["juros"] = {
                "codigo_tipo_juros": (
                    cnab_config.boleto_interest_code_id.code
                    if cnab_config.boleto_interest_code_id
                    else "90"
                ),
                "quantidade_dias_juros": 0,
                "valor_juros": self._format_amount(
                    line.interest_value or line.amount_interest or 0
                ),
                "percentual_juros": self._format_percent(line.percent_interest or 0),
                "data_juros": due_date,
            }
        if line.fee_value:
            payload["dado_boleto"]["multa"] = {
                "codigo_tipo_multa": (
                    cnab_config.boleto_fee_code_id.code
                    if cnab_config.boleto_fee_code_id
                    else "01"
                ),
                "quantidade_dias_multa": 0,
                "valor_multa": self._format_amount(line.fee_value),
                "percentual_multa": self._format_percent(0),
            }
        if cnab_config.boleto_protest_code_id or cnab_config.boleto_days_protest:
            payload["dado_boleto"]["protesto"] = {
                "codigo_tipo_protesto": int(
                    cnab_config.boleto_protest_code_id.code
                    if cnab_config.boleto_protest_code_id
                    else 0
                ),
                "quantidade_dias_protesto": int(cnab_config.boleto_days_protest or 0),
                "protesto_falimentar": False,
            }

        return payload

    def _get_person_type_payload(self, partner):
        """Build the person type payload for Itaú API.

        Args:
            partner (res.partner): Partner to build the payload from.

        Returns:
            dict: Person type payload with document numbers.
        """
        _logger.info(
            "Building person type payload for partner %s.", partner.display_name
        )
        cnpj_cpf = misc.punctuation_rm(partner.cnpj_cpf or "")
        if partner.is_company or partner.company_type == "company":
            return {
                "codigo_tipo_pessoa": "J",
                "numero_cadastro_pessoa_fisica": "",
                "numero_cadastro_nacional_pessoa_juridica": cnpj_cpf,
            }
        return {
            "codigo_tipo_pessoa": "F",
            "numero_cadastro_pessoa_fisica": cnpj_cpf,
            "numero_cadastro_nacional_pessoa_juridica": "",
        }

    def _get_address_payload(self, partner):
        """Build address payload for Itaú API.

        Args:
            partner (res.partner): Partner to build the address from.

        Returns:
            dict: Address payload with logradouro, bairro, cidade, UF, and CEP.
        """
        _logger.info("Building address payload for partner %s.", partner.display_name)
        if partner.street_name and partner.street_number:
            logradouro = f"{partner.street_name}, {partner.street_number}"
        else:
            logradouro = partner.street or ""
        return {
            "nome_logradouro": logradouro,
            "nome_bairro": partner.district or "",
            "nome_cidade": partner.city_id.name or partner.city or "",
            "sigla_UF": partner.state_id.code or "",
            "numero_CEP": misc.punctuation_rm(partner.zip or ""),
        }

    def _get_selection_label(self, record, field_name):
        """Resolve the selection label for a given field.

        Args:
            record (models.Model): Record that owns the selection field.
            field_name (str): Name of the selection field.

        Returns:
            str: Label for the selected value or empty string.
        """
        _logger.info("Resolving selection label for field %s.", field_name)
        field = record._fields.get(field_name)
        if not field:
            return ""
        selection = dict(field.selection or [])
        return selection.get(getattr(record, field_name), "")

    def _format_amount(self, value):
        """Format float values as a string with two decimals."""
        _logger.info("Formatting amount value for Itaú payload.")
        return f"{value:.2f}"

    def _format_percent(self, value):
        """Format percentage values with five decimals."""
        _logger.info("Formatting percent value for Itaú payload.")
        return f"{value:.5f}"
