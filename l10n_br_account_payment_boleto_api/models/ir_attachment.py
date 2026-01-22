# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class IrAttachment(models.Model):
    """Expose JSON payload content for attachments."""

    _inherit = "ir.attachment"

    json_content = fields.Text(
        string="JSON Content",
        compute="_compute_json_content",
        readonly=True,
    )

    def _compute_json_content(self):
        for attachment in self:
            attachment.json_content = False
            if (
                attachment.type != "binary"
                or not attachment.mimetype
                or "json" not in attachment.mimetype.lower()
            ):
                continue
            raw = attachment.with_context(bin_size=False).raw or b""
            attachment.json_content = raw.decode("utf-8")
