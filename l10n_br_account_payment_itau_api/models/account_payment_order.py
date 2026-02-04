# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from erpbrasil.base import misc

from odoo import _, fields, models
from odoo.exceptions import UserError

from .itau_api_client import ItauAPIClient

_logger = logging.getLogger(__name__)


class AccountPaymentOrder(models.Model):
    """Itaú-specific boleto API behavior for payment orders."""

    _inherit = "account.payment.order"

    def action_registrar_boleto(self):
        """Register boleto using the Itaú API implementation."""
        return super().action_registrar_boleto()

    def _validate_boleto_api_order(self, cnab_config):
        """Validate Itaú API settings before emission."""
        _logger.info("Validating Itaú API configuration for %s.", cnab_config.name)
        if cnab_config.cnab_processor != "itau_api":
            raise UserError(_("CNAB processor is not configured for Itaú API."))
        if not cnab_config.itau_api_url:
            raise UserError(_("Itaú API URL is not configured."))

    def _get_boleto_api_client(self, cnab_config):
        """Return the Itaú API client."""
        return ItauAPIClient(cnab_config)

    def _prepare_boleto_payload(self, line, move, partner, cnab_config):
        """Prepare Itaú boleto payload from payment line data."""
        return self._prepare_itau_boleto_payload(line, move, partner, cnab_config)

    def _handle_boleto_response(self, line, response_data):
        """Persist Itaú response data on payment line."""
        cnab_state = "accepted" if response_data.success else "not_accepted"
        if line.move_line_id:
            line.move_line_id.cnab_state = cnab_state
            if response_data.success:
                line.move_line_id.payment_situation = "aberta"
        line.write(
            {
                "boleto_status": "emitido" if response_data.success else "erro",
            }
        )

    def _post_boleto_message(self, partner, response_data):
        """Post a chatter message after Itaú boleto emission."""
        self.message_post(
            body=_(
                "Boleto Itaú emitted for %(partner)s. "
                "Return code: %(code)s. Message: %(msg)s"
            )
            % {
                "partner": partner.display_name,
                "code": response_data.return_code or "-",
                "msg": response_data.return_msg or "-",
            }
        )

    def action_consultar_boleto(self):
        """Consult Itaú boletos using the generic boleto API flow."""
        return super().action_consultar_boleto()

    def _prepare_itau_boleto_payload(self, line, move, partner, cnab_config):
        """Prepare Itaú boleto payload from payment line data."""
        _logger.info("Preparing Itaú boleto payload for invoice %s.", move.display_name)
        company_partner = self.company_id.partner_id
        amount = line.amount_currency or move.amount_total
        due_date = move.invoice_date_due.isoformat()
        issue_date = (
            move.invoice_date or move.date or fields.Date.context_today(self)
        ).isoformat()

        payload = {
            "data": {
                "etapa_processo_boleto": "efetivacao",
                "codigo_canal_operacao": "API",
                "beneficiario": {
                    "id_beneficiario": cnab_config.cnab_company_bank_code
                    or cnab_config.convention_code
                    or misc.punctuation_rm(company_partner.cnpj_cpf or ""),
                },
                "dado_boleto": {
                    "descricao_instrumento_cobranca": "boleto",
                    "tipo_boleto": "a vista",
                    "codigo_carteira": cnab_config.boleto_wallet or "",
                    "valor_total_titulo": self._format_amount_cents(amount),
                    "codigo_especie": cnab_config.boleto_species or "",
                    "valor_abatimento": self._format_amount_cents(line.rebate_value)
                    if line.rebate_value
                    else "000",
                    "data_emissao": issue_date,
                    "indicador_pagamento_parcial": "true"
                    if cnab_config.itau_partial_payment
                    else "false",
                    "quantidade_maximo_parcial": str(
                        cnab_config.itau_partial_payment_max or 0
                    ),
                    "pagador": {
                        "pessoa": {
                            "nome_pessoa": partner.legal_name or partner.name or "",
                            "tipo_pessoa": self._get_person_type_payload(partner),
                        },
                        "endereco": self._get_address_payload(partner),
                    },
                    "dados_individuais_boleto": [
                        {
                            "numero_nosso_numero": self._format_our_number(
                                line.own_number
                            ),
                            "data_vencimento": due_date,
                            "valor_titulo": self._format_amount_cents(amount),
                            "texto_uso_beneficiario": line.company_title_identification
                            or move.ref
                            or "",
                            "texto_seu_numero": line.document_number or move.name or "",
                        }
                    ],
                    "multa": {
                        "codigo_tipo_multa": (
                            cnab_config.boleto_fee_code_id.code
                            if cnab_config.boleto_fee_code_id
                            else "02"
                        ),
                        "quantidade_dias_multa": "1"
                        if cnab_config.boleto_fee_perc
                        else "0",
                        "percentual_multa": self._format_percent_itau(
                            cnab_config.boleto_fee_perc or 0
                        ),
                    },
                    "juros": {
                        "codigo_tipo_juros": (
                            cnab_config.boleto_interest_code_id.code
                            if cnab_config.boleto_interest_code_id
                            else "90"
                        ),
                        "quantidade_dias_juros": "1"
                        if cnab_config.boleto_interest_perc
                        else "0",
                        "percentual_juros": self._format_percent_itau(
                            cnab_config.boleto_interest_perc or 0
                        ),
                    },
                    "recebimento_divergente": {
                        "codigo_tipo_autorizacao": (
                            cnab_config.itau_recebimento_divergente_code or "03"
                        )
                    },
                    "desconto_expresso": "true"
                    if cnab_config.itau_desconto_expresso
                    else "false",
                },
            }
        }

        if line.discount_value:
            payload["data"]["dado_boleto"]["desconto"] = {
                "codigo_tipo_desconto": (
                    cnab_config.boleto_discount_code_id.code
                    if cnab_config.boleto_discount_code_id
                    else "01"
                ),
                "descontos": [
                    {
                        "data_desconto": due_date,
                        "valor_desconto": self._format_amount_cents(
                            line.discount_value
                        ),
                    }
                ],
            }
        if cnab_config.boleto_protest_code_id or cnab_config.boleto_days_protest:
            payload["data"]["dado_boleto"]["protesto"] = {
                "codigo_tipo_protesto": str(
                    cnab_config.boleto_protest_code_id.code
                    if cnab_config.boleto_protest_code_id
                    else "0"
                ),
                "quantidade_dias_protesto": str(cnab_config.boleto_days_protest or 0),
                "protesto_falimentar": False,
            }

        return payload

    def _prepare_boleto_query_params(self, line, cnab_config):
        """Prepare Itaú API query parameters for boleto consultation."""
        _logger.info(
            "Preparing Itaú boleto consultation parameters for %s.",
            line.display_name,
        )
        nosso_numero = line.nosso_numero or line.own_number
        if not nosso_numero:
            raise UserError(_("Payment line %s has no nosso número.") % line.name)
        id_beneficiario = (
            cnab_config.cnab_company_bank_code
            or cnab_config.convention_code
            or self.company_id.partner_id.cnpj_cpf
        )
        if not id_beneficiario:
            raise UserError(_("CNAB beneficiary id is not configured."))
        return {
            "id_beneficiario": id_beneficiario,
            "nosso_numero": self._format_our_number(nosso_numero),
        }

    def _handle_boleto_consulta_response(self, line, response_data):
        """Persist Itaú consultation response on the payment line."""
        status = response_data.get("status") or response_data.get("situacao")
        nosso_numero = response_data.get("nosso_numero") or response_data.get(
            "nossoNumero"
        )
        values = {}
        if status:
            values["itau_boleto_status"] = status
        if nosso_numero:
            values["nosso_numero"] = nosso_numero
        if values:
            line.write(values)

    def _post_boleto_consulta_message(self, line, response_data):
        """Post a chatter message after Itaú boleto consultation."""
        self.message_post(
            body=_(
                "Boleto Itaú consulted for %(line)s. "
                "Status: %(status)s. Nosso número: %(nosso)s."
            )
            % {
                "line": line.display_name,
                "status": response_data.get("status")
                or response_data.get("situacao")
                or "-",
                "nosso": response_data.get("nosso_numero")
                or response_data.get("nossoNumero")
                or "-",
            }
        )

    def _get_person_type_payload(self, partner):
        """Build the person type payload for Itaú API."""
        _logger.info(
            "Building person type payload for partner %s.", partner.display_name
        )
        cnpj_cpf = misc.punctuation_rm(partner.cnpj_cpf or "")
        if partner.is_company or partner.company_type == "company":
            return {
                "codigo_tipo_pessoa": "J",
                "numero_cadastro_nacional_pessoa_juridica": cnpj_cpf,
            }
        return {
            "codigo_tipo_pessoa": "F",
            "numero_cadastro_pessoa_fisica": cnpj_cpf,
        }

    def _get_address_payload(self, partner):
        """Build address payload for Itaú API."""
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
        """Resolve the selection label for a given field."""
        _logger.info("Resolving selection label for field %s.", field_name)
        field = record._fields.get(field_name)
        if not field:
            return ""
        selection = dict(field.selection or [])
        return selection.get(getattr(record, field_name), "")

    def _format_amount_cents(self, value):
        """Format amount as cents with zero padding (17 digits)."""
        _logger.info("Formatting amount value for Itaú payload.")
        cents = int(round((value or 0) * 100))
        return str(cents).zfill(17)

    def _format_percent_itau(self, value):
        """Format percent for Itaú payload with 6 integer + 6 decimals."""
        _logger.info("Formatting percent value for Itaú payload.")
        percent = int(round((value or 0) * 100000))
        return str(percent).zfill(12)

    def _format_our_number(self, value):
        """Format nosso numero with zero padding to 8 digits."""
        _logger.info("Formatting nosso numero for Itaú payload.")
        if not value:
            return ""
        digits = "".join(char for char in str(value) if char.isdigit())
        return digits.zfill(8)
