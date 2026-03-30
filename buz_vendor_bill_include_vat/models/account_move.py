from odoo import api, fields, models, _
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    is_vat_included = fields.Boolean(
        string='VAT Included in Price',
        default=False,
        copy=False,
        help="Indicates if VAT has been calculated and included in the line prices."
    )

    def action_include_vat_into_price(self):
        for move in self:
            if move.state != 'draft':
                raise UserError(_("Only draft bills allowed"))
            
            if move.move_type not in ['in_invoice', 'in_refund']:
                raise UserError(_("Only vendor bills allowed"))
                
            if move.is_vat_included:
                raise UserError(_("VAT already included"))

            lines_updated = False
            for line in move.invoice_line_ids:
                if line.tax_ids:
                    # Validate Company Isolation
                    if line.tax_ids.filtered(lambda t: t.company_id != move.company_id):
                        raise UserError(_("Tax company mismatch"))

                    # Filter valid taxes
                    valid_taxes = line.tax_ids.filtered(lambda t: not t.price_include and t.amount > 0)
                    
                    if not valid_taxes:
                        continue

                    # Tax Computation (Odoo Engine)
                    taxes_res = valid_taxes.compute_all(
                        line.price_unit,
                        currency=move.currency_id,
                        quantity=1.0,
                        product=line.product_id,
                        partner=move.partner_id,
                    )

                    tax_amount = sum(t['amount'] for t in taxes_res.get('taxes', []))

                    # Update Logic
                    new_price = line.price_unit + tax_amount
                    line.write({
                        'price_unit': new_price,
                        'tax_ids': [(5, 0, 0)]
                    })
                    lines_updated = True

            if lines_updated:
                # Recompute
                if hasattr(move, '_recompute_dynamic_lines'):
                    move._recompute_dynamic_lines(recompute_all_taxes=True)

                move.is_vat_included = True
                
                # Audit Log
                move.message_post(body=_("VAT has been included into price and removed from lines"))
