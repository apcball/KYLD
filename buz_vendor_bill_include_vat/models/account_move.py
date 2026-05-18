from odoo import models, fields
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_vat_included = fields.Boolean(
        copy=False,
        help="Indicates if VAT has been included in the price of lines"
    )

    def _get_processable_vat_lines(self, lines):
        """Return invoice lines that can actually be processed for VAT inclusion."""
        return lines.filtered(
            lambda line: line.tax_ids
            and line.display_type not in ('line_section', 'line_note')
            and line.quantity != 0
        )

    def _apply_vat_inclusion(self, lines):
        """Core VAT-in-price logic shared by selected-lines and include-all actions."""
        self.ensure_one()

        total_vat_moved = 0.0
        line_updates = []

        for line in lines:
            # Calculate the discounted unit price first so compute_all sees the real taxable base.
            price_unit_after_discount = line.price_unit * (1 - line.discount / 100.0)

            tax_data = line.tax_ids.compute_all(
                price_unit=price_unit_after_discount,
                currency=self.currency_id,
                quantity=line.quantity,
                product=line.product_id,
                partner=self.partner_id,
            )

            vat_tax_ids = self.env['account.tax']
            vat_amount = 0.0

            for tax_dict in tax_data['taxes']:
                tax = self.env['account.tax'].browse(tax_dict['id'])
                if (
                    tax_dict['amount'] > 0
                    and tax.tax_group_id
                    and 'vat' in tax.tax_group_id.name.lower()
                    and not tax.price_include
                ):
                    vat_amount += tax_dict['amount']
                    vat_tax_ids |= tax

            if not vat_amount:
                continue

            remaining_tax_ids = line.tax_ids - vat_tax_ids

            # Rebuild the unit price so the tax amount becomes part of the line price.
            if line.quantity and line.discount != 100.0:
                new_subtotal = tax_data['total_excluded'] + vat_amount
                new_price_unit = new_subtotal / line.quantity / (1 - line.discount / 100.0)
            else:
                new_price_unit = 0.0

            line_updates.append((1, line.id, {
                'price_unit': new_price_unit,
                'original_price_unit': line.price_unit,
                'vat_included_amount': vat_amount,
                'original_tax_ids': [(6, 0, vat_tax_ids.ids)],
                'tax_ids': [(6, 0, remaining_tax_ids.ids)],
            }))
            total_vat_moved += vat_amount

        if not line_updates:
            raise UserError("No taxable invoice lines were found to process.")

        self.with_context(check_move_validity=False).write({'invoice_line_ids': line_updates})
        self.is_vat_included = True

        message = (
            f"VAT included into {len(line_updates)} lines successfully. "
            f"Total VAT moved: {self.currency_id.format(total_vat_moved)}"
        )
        self.message_post(body=message)
        return True

    def action_include_vat_in_price(self):
        """Button action to include VAT in price for selected lines"""
        self.ensure_one()

        # Validate move state and type
        if self.move_type not in ('in_invoice', 'in_refund'):
            raise UserError("This action is only allowed for vendor bills and vendor credit notes.")
        if self.state != 'draft':
            raise UserError("This action is only allowed for draft moves.")
        if self.is_vat_included:
            raise UserError("This move has already been processed.")

        # Get selected lines (lines with include_vat_cost checked)
        selected_lines = self.invoice_line_ids.filtered(lambda line: line.include_vat_cost)

        if not selected_lines:
            raise UserError("Please select at least one line to include VAT in price.")

        processable_lines = self._get_processable_vat_lines(selected_lines)
        if not processable_lines:
            raise UserError("Selected lines do not contain any taxable invoice lines.")

        return self._apply_vat_inclusion(processable_lines)

    def action_include_vat_all(self):
        """Include VAT in price for all taxable invoice lines."""
        self.ensure_one()

        if self.move_type not in ('in_invoice', 'in_refund'):
            raise UserError("This action is only allowed for vendor bills and vendor credit notes.")
        if self.state != 'draft':
            raise UserError("This action is only allowed for draft moves.")
        if self.is_vat_included:
            raise UserError("This move has already been processed.")

        processable_lines = self._get_processable_vat_lines(self.invoice_line_ids)
        if not processable_lines:
            raise UserError("No taxable invoice lines were found to process.")

        return self._apply_vat_inclusion(processable_lines)

    def action_restore_vat(self):
        """Button action to restore VAT to separate tax lines"""
        self.ensure_one()

        # Validate move state and type
        if self.move_type not in ('in_invoice', 'in_refund'):
            raise UserError("This action is only allowed for vendor bills and vendor credit notes.")
        if self.state != 'draft':
            raise UserError("This action is only allowed for draft moves.")
        if not self.is_vat_included:
            raise UserError("This move has not been processed yet.")

        # Get lines that were processed
        processed_lines = self.invoice_line_ids.filtered(lambda line: line.original_price_unit)

        if not processed_lines:
            raise UserError("No lines were previously processed.")

        # Restore original values
        total_vat_restored = 0
        line_updates = []

        for line in processed_lines:
            # Restore original price unit
            if line.original_price_unit:
                # Calculate the original VAT amount from the stored value
                original_vat_amount = line.vat_included_amount

                # Restore original taxes (current taxes + original VAT taxes)
                restored_tax_ids = line.tax_ids | line.original_tax_ids

                line_updates.append((1, line.id, {
                    'price_unit': line.original_price_unit,
                    'original_price_unit': 0.0,
                    'vat_included_amount': 0.0,
                    'tax_ids': [(6, 0, restored_tax_ids.ids)],
                    'original_tax_ids': [(5, 0, 0)],  # Clear the original tax IDs
                }))

                total_vat_restored += original_vat_amount

        # Apply all line updates in batch
        if line_updates:
            self.with_context(check_move_validity=False).write({'invoice_line_ids': line_updates})

        # Mark the move as not processed
        self.is_vat_included = False

        # Odoo 17 automatically computes taxes when price/taxes are changed.
        # self._recompute_dynamic_lines(recompute_all_taxes=True)

        # Post message to chatter
        message = f"VAT restored to {len(processed_lines)} lines successfully. Total VAT restored: {self.currency_id.format(total_vat_restored)}"
        self.message_post(body=message)

        return True
