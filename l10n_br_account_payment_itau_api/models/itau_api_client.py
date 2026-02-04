# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import logging
import time
import uuid
from tempfile import NamedTemporaryFile

import requests
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)
from cryptography.hazmat.primitives.serialization.pkcs12 import (
    load_key_and_certificates,
)
from erpbrasil.assinatura import certificado as erpbrasil_certificado

_logger = logging.getLogger(__name__)


class ItauAPIClient:
    """Helper class to communicate with Itaú API for boleto emission."""

    def __init__(self, cnab_config):
        """Initialize Itaú API client with CNAB config.

        Args:
            cnab_config (l10n_br_cnab.config): CNAB configuration with Itaú data.
        """
        _logger.info(
            "Initializing Itaú API client for CNAB config %s.", cnab_config.name
        )
        self.cnab_config = cnab_config
        self.base_url = cnab_config.itau_api_url
        self.client_id = cnab_config.itau_client_id
        self.client_secret = cnab_config.itau_client_secret
        self._access_token = None
        self._access_token_expires_at = 0

    def get_certificate(self):
        """Load certificate from CNAB config and return PEM paths.

        Uses the same certificate loading mechanism as NFS-e Paulistana
        (erpbrasil.assinatura Certificado) and prepares PEM files for mTLS.

        Returns:
            tuple[str, str]: Temporary paths for certificate and private key.

        Raises:
            ValueError: When the certificate cannot be loaded.
        """
        _logger.info(
            "Loading Itaú certificate from CNAB config %s.", self.cnab_config.name
        )
        certificate = self.cnab_config.itau_certificate_id
        if not certificate or not certificate.file:
            raise ValueError("Itaú certificate not found in CNAB configuration.")

        try:
            erpbrasil_certificado.Certificado(
                arquivo=certificate.file,
                senha=certificate.password,
            )
        except Exception as exc:
            _logger.exception("Failed to load certificate via erpbrasil.assinatura.")
            raise ValueError("Invalid Itaú certificate.") from exc

        cert_file = base64.b64decode(certificate.file)
        password = certificate.password.encode() if certificate.password else None
        key, cert, _additional_certs = load_key_and_certificates(cert_file, password)
        if not key or not cert:
            raise ValueError("Certificate or key could not be extracted from PKCS#12.")

        cert_temp = NamedTemporaryFile(delete=False, suffix=".pem")
        key_temp = NamedTemporaryFile(delete=False, suffix=".key")
        cert_temp.write(cert.public_bytes(Encoding.PEM))
        key_temp.write(
            key.private_bytes(
                Encoding.PEM,
                PrivateFormat.TraditionalOpenSSL,
                NoEncryption(),
            )
        )
        cert_temp.flush()
        key_temp.flush()
        cert_temp.close()
        key_temp.close()
        _logger.info("Generated PEM files for Itaú API certificate.")

        return cert_temp.name, key_temp.name

    def emitir_boleto(self, payload):
        """Emit a boleto using Itaú API with mTLS authentication.

        Args:
            payload (dict): Boleto payload to be sent.

        Returns:
            dict: Response data with keys "nosso_numero" and "url_boleto".

        Raises:
            RuntimeError: When the API call fails or returns invalid JSON.
        """
        _logger.info("Sending boleto payload to Itaú API.")
        cert_path, key_path = self.get_certificate()
        token = self._get_access_token()
        url = f"{self.base_url.rstrip('/')}/boletos"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-itau-correlationID": str(uuid.uuid4()),
        }
        if self.client_id:
            headers["x-itau-apikey"] = self.client_id
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = requests.post(
                url,
                json=payload,
                cert=(cert_path, key_path),
                headers=headers,
                timeout=60,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            _logger.exception("Itaú API request failed.")
            raise RuntimeError(f"Itaú API request failed: {exc}") from exc

        response_text = response.text
        response_json = {}
        try:
            response_json = response.json()
        except ValueError:
            _logger.exception("Invalid JSON response from Itaú API.")

        return self._build_boleto_return(
            response.status_code,
            response_text,
            response_json,
        )

    def _build_boleto_return(self, status_code, response_text, response_json):
        """Build a boleto return record from the Itaú API response."""
        return_msg = (
            response_json.get("mensagem") if isinstance(response_json, dict) else None
        )
        data = response_json.get("data", {}) if isinstance(response_json, dict) else {}
        beneficiario = data.get("beneficiario", {}) if isinstance(data, dict) else {}
        dado_boleto = data.get("dado_boleto", {}) if isinstance(data, dict) else {}
        dados_individuais = dado_boleto.get("dados_individuais_boleto")
        if isinstance(dados_individuais, list):
            dados_individuais = dados_individuais[0] if dados_individuais else {}
        if not isinstance(dados_individuais, dict):
            dados_individuais = {}

        values = {
            "return_code": str(status_code),
            "success": status_code == 200,
            "return_msg_detail": response_text,
            "return_msg": return_msg or "",
        }
        if status_code == 200:
            values.update(
                {
                    "beneficiaryid": beneficiario.get("id_beneficiario", ""),
                    "boletoid": dados_individuais.get("id_boleto_individual", ""),
                    "barcode_typed": dados_individuais.get(
                        "numero_linha_digitavel",
                        "",
                    ),
                    "barcode": dados_individuais.get("codigo_barras", ""),
                }
            )

        return self.cnab_config.env["l10n_br_account_payment_boleto_api.return"].create(
            values
        )

    def consultar_boleto(self, query_params):
        """Consult a boleto using Itaú API with mTLS authentication.

        Args:
            query_params (dict): Query parameters to be sent.

        Returns:
            dict: Response data returned by Itaú API.

        Raises:
            RuntimeError: When the API call fails or returns invalid JSON.
        """
        _logger.info("Consulting boleto in Itaú API.")
        cert_path, key_path = self.get_certificate()
        token = self._get_access_token()
        url = f"{self.base_url.rstrip('/')}/boletos"
        headers = {
            "Accept": "application/json",
            "x-itau-correlationID": str(uuid.uuid4()),
        }
        if self.client_id:
            headers["x-itau-apikey"] = self.client_id
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = requests.get(
                url,
                params=query_params,
                cert=(cert_path, key_path),
                headers=headers,
                timeout=60,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            _logger.exception("Itaú API consultation request failed.")
            raise RuntimeError(f"Itaú API request failed: {exc}") from exc

        try:
            response_data = response.json()
        except ValueError as exc:
            _logger.exception("Invalid JSON response from Itaú API.")
            raise RuntimeError("Invalid JSON response from Itaú API.") from exc

        return {
            "response_data": response_data,
            "status": response_data.get("status") or response_data.get("situacao"),
            "nosso_numero": response_data.get("nosso_numero")
            or response_data.get("nossoNumero"),
        }

    def _get_access_token(self):
        """Fetch OAuth token using client credentials."""
        now = time.time()
        if self._access_token and now < self._access_token_expires_at:
            return self._access_token
        if not self.client_id or not self.client_secret:
            raise ValueError("Itaú API client credentials are not configured.")
        url = "https://sandbox.devportal.itau.com.br/api/oauth/jwt"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        try:
            response = requests.post(url, data=payload, timeout=60)
            response.raise_for_status()
        except requests.RequestException as exc:
            _logger.exception("Itaú API token request failed.")
            raise RuntimeError(f"Itaú API token request failed: {exc}") from exc

        try:
            token_data = response.json()
        except ValueError as exc:
            _logger.exception("Invalid JSON response from Itaú API token endpoint.")
            raise RuntimeError(
                "Invalid JSON response from Itaú API token endpoint."
            ) from exc

        access_token = token_data.get("access_token")
        if not access_token:
            raise RuntimeError("Missing access_token in Itaú API token response.")
        expires_in = token_data.get("expires_in") or 300
        try:
            expires_in = int(expires_in)
        except (TypeError, ValueError):
            expires_in = 300
        # refresh one minute before expiry
        self._access_token = access_token
        self._access_token_expires_at = now + max(expires_in - 60, 0)
        return access_token
