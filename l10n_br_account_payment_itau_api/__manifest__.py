# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Itaú API - Boletos",
    "summary": "Emit boletos via Itaú API",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "author": "Akretion, Odoo Community Association (OCA)",
    "maintainers": ["mtolent"],
    "website": "https://github.com/OCA/l10n-brazil",
    "depends": [
        "l10n_br_account_payment_brcobranca",
        "l10n_br_fiscal_certificate",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/account_journal.xml",
        "views/account_move_view.xml",
        "views/account_payment_line.xml",
        "views/account_payment_mode.xml",
        "views/l10n_br_cnab_config_view.xml",
        "views/account_payment_order.xml",
        "views/res_config_settings_views.xml",
    ],
    "external_dependencies": {
        "python": [
            "cryptography",
            "erpbrasil.assinatura",
            "requests",
        ]
    },
}
