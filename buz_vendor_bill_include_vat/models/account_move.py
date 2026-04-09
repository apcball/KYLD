from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError
from odoo.tools import float_round


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_vat_included = fields.Boolean(
        string='VAT Included in Price',
        default=False,
        copy=False,
        help="Indicates if VAT has been calculated and included in the line prices.",
    )

    def action_include_vat_into_price(self):
        """Include VAT into price_unit and remove tax_ids from bill lines.

        Recalculates each line's price_unit to be tax-inclusive, then removes
        the taxes so the line total stays the same. All changes are batched
        into a single ``move.write()`` so that Odoo 17's
        ``_sync_dynamic_lines`` properly recomputes payment-term and tax
        journal-item lines, keeping the entry balanced.

        Rounding strategy
        -----------------
        ``new_price_unit`` is rounded to **Product Price** decimal precision
        (typically 4 dp) rather than the currency's decimal places (2 dp).
        This prevents the situation where ``price_unit × qty`` differs from
        ``total_included`` after rounding, which would produce an unbalanced
        journal entry and block the bill from being posted.
        """
        # Fetch Product Price decimal precision once (e.g. 4 dp)
        price_dp = self.env['decimal.precision'].precision_get('Product Price')

        for move in self:
            if move.state != 'draft':
                raise UserError(_("Only draft bills can be modified."))
            if move.move_type not in ('in_invoice', 'in_refund'):
                raise UserError(_("This action is only available for vendor bills."))
            if move.is_vat_included:
                raise UserError(_("VAT has already been included in the price."))

            line_updates = []
            has_changes = False

            for line in move.invoice_line_ids:
                if not line.tax_ids:
                    continue

                # Only process non-inclusive taxes with positive amounts
                taxes_to_include = line.tax_ids.filtered(
                    lambda t: not t.price_include and t.amount > 0
                )
                if not taxes_to_include:
                    continue

                # Compute tax using the FULL line context (quantity, discount)
                line_discount_price_unit = line.price_unit * (1 - (line.discount / 100.0))
                taxes_res = taxes_to_include.compute_all(
                    line_discount_price_unit,
                    currency=move.currency_id,
                    quantity=line.quantity,
                    product=line.product_id,
                    partner=move.partner_id,
                    is_refund=move.move_type == 'in_refund',
                )

                # Back-calculate the new price_unit from the tax-inclusive total.
                # Use total_included which is already rounded to currency precision
                # by compute_all, so the resulting price_unit reconstructs back
                # to that exact amount when multiplied by quantity/discount factor.
                total_included = taxes_res['total_included']
                if line.quantity and line.quantity != 0:
                    if line.discount and line.discount != 0:
                        # Reverse the discount: price_unit * (1 - disc%) * qty = total
                        new_price_unit = total_included / (
                            line.quantity * (1 - line.discount / 100.0)
                        )
                    else:
                        new_price_unit = total_included / line.quantity
                else:
                    new_price_unit = line.price_unit

                # Round to Product Price precision (usually 4 dp) rather than
                # currency precision (2 dp). This keeps price_unit * qty ≈
                # total_included within the currency's rounding tolerance and
                # prevents a debit/credit imbalance when posting the bill.
                new_price_unit = float_round(new_price_unit, precision_digits=price_dp)

                line_updates.append(Command.update(line.id, {
                    'price_unit': new_price_unit,
                    'tax_ids': [Command.clear()],
                }))
                has_changes = True

            if has_changes:
                # Single write triggers _sync_dynamic_lines which recomputes
                # tax lines and payment term (payable) lines correctly
                move.write({
                    'invoice_line_ids': line_updates,
                    'is_vat_included': True,
                })
                move.message_post(
                    body=_(
                        "VAT has been included in line prices and tax lines removed."
                    )
                )
