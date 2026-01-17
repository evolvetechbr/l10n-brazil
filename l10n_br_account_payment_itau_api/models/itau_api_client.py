# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import json
import logging
import os
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
        url = f"{self.base_url.rstrip('/')}/boletos"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-itau-correlationID": str(uuid.uuid4()),
        }
        if self.client_id:
            headers["x-itau-apikey"] = self.client_id

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

        try:
            response_data = response.json()
        except ValueError as exc:
            _logger.exception("Invalid JSON response from Itaú API.")
            raise RuntimeError("Invalid JSON response from Itaú API.") from exc

        os.makedirs("/opt/odoo/data", exist_ok=True)
        response_path = "/opt/odoo/data/response.json"
        with open(response_path, "w", encoding="utf-8") as response_file:
            json.dump(response_data, response_file, ensure_ascii=True, indent=2)
        _logger.info("Saved Itaú API response to %s.", response_path)

        return {
            "nosso_numero": response_data.get("nosso_numero")
            or response_data.get("nossoNumero"),
            "url_boleto": response_data.get("url_boleto")
            or response_data.get("urlBoleto")
            or response_data.get("linkBoleto"),
        }
