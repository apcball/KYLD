from odoo import models, fields


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    include_vat_cost = fields.Boolean(
        string="Include VAT",
        help="If checked, VAT of this line will be moved into cost."
    )
    original_price_unit = fields.Float(
        copy=False,
        help="Original price unit before VAT was included"
    )
    vat_included_amount = fields.Monetary(
        copy=False,
        help="VAT amount that was included in the price"
    )
    original_tax_ids = fields.Many2many(
        'account.tax',
        relation='account_move_line_original_tax_rel',
        column1='line_id',
        column2='tax_id',
        string='Original Taxes',
        copy=False,
        help='Original tax IDs before VAT inclusion, used for restoration'
    )
