# Copyright 2026 Ecosoft Co., Ltd (https://ecosoft.co.th/)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import fields, models, tools


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    wht_tax_id = fields.Many2one(
        comodel_name="account.withholding.tax",
        string="WHT",
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        help="Withholding tax to carry over to the vendor bill line.",
    )

    def _auto_init(self):
        """Ensure the stored WHT field exists even on databases that missed an upgrade."""
        if not tools.column_exists(self.env.cr, self._table, "wht_tax_id"):
            self.env.cr.execute(
                f'ALTER TABLE "{self._table}" ADD COLUMN "wht_tax_id" integer'
            )
        return super()._auto_init()

    def _prepare_account_move_line(self, move=False):
        vals = super()._prepare_account_move_line(move=move)
        if (
            not vals.get("display_type")
            and self.wht_tax_id
        ):
            vals["wht_tax_id"] = self.wht_tax_id.id
        return vals
