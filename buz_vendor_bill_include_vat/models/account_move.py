from odoo import models, fields
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_vat_included = fields.Boolean(
        copy=False,
        help="Indicates if VAT has been included in the price of lines"
    )

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
        
        # Process each selected line
        total_vat_moved = 0
        line_updates = []
        
        for line in selected_lines:
            # Skip lines that don't have taxes or are display lines
            if not line.tax_ids or line.display_type in ('line_section', 'line_note') or line.quantity == 0:
                continue
                
            # Calculate price_unit_after_discount
            price_unit_after_discount = line.price_unit * (1 - line.discount / 100.0)
            
            # Calculate VAT amount
            tax_data = line.tax_ids.compute_all(
                price_unit=price_unit_after_discount,
                currency=self.currency_id,
                quantity=line.quantity,
                product=line.product_id,
                partner=self.partner_id,
            )
            
            # Find VAT taxes only
            vat_taxes = []
            vat_amount = 0
            vat_tax_ids = self.env['account.tax']
            
            for tax_dict in tax_data['taxes']:
                tax = self.env['account.tax'].browse(tax_dict['id'])
                # Only include taxes that are VAT and not price_include
                if (tax_dict['amount'] > 0
                    and tax.tax_group_id
                    and 'vat' in tax.tax_group_id.name.lower()
                    and not tax.price_include):
                    vat_taxes.append(tax_dict)
                    vat_amount += tax_dict['amount']
                    vat_tax_ids |= tax
            
            if vat_amount > 0:
                # Calculate new price_unit with VAT included
                # We need to recalculate the price_unit to account for the VAT
                new_subtotal = tax_data['total_excluded'] + vat_amount
                new_price_unit = new_subtotal / line.quantity / (1 - line.discount / 100.0) if line.quantity and line.discount != 100.0 else 0.0
                
                # Calculate remaining taxes (non-VAT taxes)
                remaining_tax_ids = line.tax_ids - vat_tax_ids
                
                # Store original values and update line
                line_updates.append((1, line.id, {
                    'price_unit': new_price_unit,
                    'original_price_unit': line.price_unit,
                    'vat_included_amount': vat_amount,
                    'original_tax_ids': [(6, 0, vat_tax_ids.ids)],
                    'tax_ids': [(6, 0, remaining_tax_ids.ids)],  # Keep only non-VAT taxes
                }))
                
                total_vat_moved += vat_amount
        
        # Apply all line updates in batch
        if line_updates:
            # We must use self.write on the invoice_line_ids field to apply the One2many commands properly
            # and to trigger Odoo's automatic tax recomputation correctly.
            self.with_context(check_move_validity=False).write({'invoice_line_ids': line_updates})
        
        # Mark the move as processed
        self.is_vat_included = True
        
        # Odoo 17 automatically computes taxes when price/taxes are changed.
        # self._recompute_dynamic_lines(recompute_all_taxes=True)
        
        # Post message to chatter
        message = f"VAT included into {len(selected_lines)} lines successfully. Total VAT moved: {self.currency_id.format(total_vat_moved)}"
        self.message_post(body=message)
        
        return True

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
