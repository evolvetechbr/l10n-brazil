# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Itaú API Client - Boletos",
    "summary": "Client helper for Itaú boleto API",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "author": "Akretion, Odoo Community Association (OCA)",
    "maintainers": ["mtolent"],
    "website": "https://github.com/OCA/l10n-brazil",
    "depends": [
        "l10n_br_account_payment_boleto_api",
        "l10n_br_fiscal_certificate",
    ],
    "data": [
        "data/l10n_br_payment_method_itau_api.xml",
        "data/cnab_codes/banco_itau_api_boleto_instructon.xml",
        "data/cnab_codes/banco_itau_api_boleto_fee_code.xml",
        "data/cnab_codes/banco_itau_api_boleto_protest_code.xml",
        "views/l10n_br_cnab_config_view.xml",
    ],
    "external_dependencies": {
        "python": [
            "cryptography",
            "erpbrasil.assinatura",
            "requests",
        ]
    },
}
