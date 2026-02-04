# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Boleto API - Boletos",
    "summary": "Emit boletos via API",
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
        "security/boleto_api_security.xml",
        "security/ir.model.access.csv",
        "views/account_journal.xml",
        "views/account_move_view.xml",
        "views/account_payment_line.xml",
        "views/account_payment_mode.xml",
        "views/ir_attachment_views.xml",
        "views/account_payment_order.xml",
        "views/boleto_api_event_views.xml",
    ],
}
