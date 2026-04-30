# -*- coding: utf-8 -*-
"""
Tests for the buz_vendor_bill_include_vat module
"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestVatInclusion(TransactionCase):
    def setUp(self):
        super().setUp()
        # Create a test partner
        self.partner = self.env['res.partner'].create({
            'name': 'Test Partner',
        })
        
        # Create a test product
        self.product = self.env['product.product'].create({
            'name': 'Test Product',
            'type': 'service',
        })
        
        # Create a test tax group for VAT
        self.tax_group_vat = self.env['account.tax.group'].create({
            'name': 'VAT',
        })
        
        # Create a test tax group for withholding
        self.tax_group_wht = self.env['account.tax.group'].create({
            'name': 'Withholding Tax',
        })
        
        # Create a test VAT tax (7%)
        self.vat_tax = self.env['account.tax'].create({
            'name': 'VAT 7%',
            'amount': 7.0,
            'amount_type': 'percent',
            'tax_group_id': self.tax_group_vat.id,
            'type_tax_use': 'purchase',
        })
        
        # Create a test withholding tax (3%)
        self.wht_tax = self.env['account.tax'].create({
            'name': 'Withholding 3%',
            'amount': 3.0,
            'amount_type': 'percent',
            'tax_group_id': self.tax_group_wht.id,
            'type_tax_use': 'purchase',
        })
        
        # Create a test company
        self.company = self.env['res.company'].create({
            'name': 'Test Company',
        })
        
    def test_vat_inclusion_basic(self):
        """Test basic VAT inclusion functionality"""
        # Create a vendor bill with a line
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.product.id,
                    'quantity': 1,
                    'price_unit': 100.0,
                    'tax_ids': [(6, 0, [self.vat_tax.id])],
                })
            ]
        })
        
        # Check initial state
        self.assertEqual(len(move.invoice_line_ids), 1)
        line = move.invoice_line_ids[0]
        self.assertEqual(line.price_unit, 100.0)
        self.assertTrue(line.tax_ids)
        
        # Select the line for VAT inclusion
        line.include_vat_cost = True
        
        # Call the action to include VAT in price
        move.action_include_vat_in_price()
        
        # Verify VAT was included
        self.assertTrue(move.is_vat_included)
        self.assertEqual(line.price_unit, 107.0)  # 100 + 7 VAT
        self.assertFalse(line.tax_ids)  # VAT should be removed
        self.assertEqual(line.original_price_unit, 100.0)
        self.assertEqual(line.vat_included_amount, 7.0)
        self.assertTrue(line.original_tax_ids)
        
    def test_vat_restoration(self):
        """Test VAT restoration functionality"""
        # Create a vendor bill with a line
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.product.id,
                    'quantity': 1,
                    'price_unit': 100.0,
                    'tax_ids': [(6, 0, [self.vat_tax.id])],
                })
            ]
        })
        
        # Select the line for VAT inclusion
        line = move.invoice_line_ids[0]
        line.include_vat_cost = True
        
        # Include VAT
        move.action_include_vat_in_price()
        
        # Verify VAT was included
        self.assertTrue(move.is_vat_included)
        self.assertEqual(line.price_unit, 107.0)
        
        # Restore VAT
        move.action_restore_vat()
        
        # Verify VAT was restored
        self.assertFalse(move.is_vat_included)
        self.assertEqual(line.price_unit, 100.0)
        self.assertTrue(line.tax_ids)  # VAT should be restored
        self.assertEqual(len(line.tax_ids), 1)
        self.assertEqual(line.tax_ids[0], self.vat_tax)
        self.assertEqual(line.original_price_unit, 0.0)
        self.assertEqual(line.vat_included_amount, 0.0)
        self.assertFalse(line.original_tax_ids)
        
    def test_vat_inclusion_with_discount(self):
        """Test VAT inclusion with discount"""
        # Create a vendor bill with a line and 10% discount
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.product.id,
                    'quantity': 1,
                    'price_unit': 100.0,
                    'discount': 10.0,  # 10% discount
                    'tax_ids': [(6, 0, [self.vat_tax.id])],
                })
            ]
        })
        
        # Check initial state
        self.assertEqual(len(move.invoice_line_ids), 1)
        line = move.invoice_line_ids[0]
        self.assertEqual(line.price_unit, 100.0)
        self.assertEqual(line.discount, 10.0)
        self.assertTrue(line.tax_ids)
        
        # Select the line for VAT inclusion
        line.include_vat_cost = True
        
        # Call the action to include VAT in price
        move.action_include_vat_in_price()
        
        # Verify VAT was included correctly with discount
        self.assertTrue(move.is_vat_included)
        # Price should be 100 * (1-0.1) = 90, then 90 + 7 VAT = 97, then 97 / (1-0.1) = 107.78
        # But we're using the correct formula: (90 + 7) / (1-0.1) = 97 / 0.9 = 107.78
        self.assertEqual(line.original_price_unit, 100.0)
        self.assertEqual(line.vat_included_amount, 7.0)
        self.assertTrue(line.original_tax_ids)
        
    def test_mixed_taxes(self):
        """Test VAT inclusion with mixed taxes (VAT + withholding)"""
        # Create a vendor bill with VAT and withholding tax
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.product.id,
                    'quantity': 1,
                    'price_unit': 100.0,
                    'tax_ids': [(6, 0, [self.vat_tax.id, self.wht_tax.id])],
                })
            ]
        })
        
        # Check initial state
        line = move.invoice_line_ids[0]
        self.assertEqual(len(line.tax_ids), 2)
        
        # Select the line for VAT inclusion
        line.include_vat_cost = True
        
        # Call the action to include VAT in price
        move.action_include_vat_in_price()
        
        # Verify VAT was included but withholding tax remains
        self.assertTrue(move.is_vat_included)
        self.assertEqual(line.price_unit, 107.0)  # 100 + 7 VAT
        self.assertEqual(len(line.tax_ids), 1)  # Only withholding tax should remain
        self.assertEqual(line.tax_ids[0], self.wht_tax)
        self.assertEqual(line.original_price_unit, 100.0)
        self.assertEqual(line.vat_included_amount, 7.0)
        self.assertTrue(line.original_tax_ids)
        
    def test_vat_inclusion_validation(self):
        """Test validation rules"""
        # Create a vendor bill
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.product.id,
                    'quantity': 1,
                    'price_unit': 100.0,
                    'tax_ids': [(6, 0, [self.vat_tax.id])],
                })
            ]
        })
        
        # Try to process a non-draft move (should fail)
        move.state = 'posted'
        with self.assertRaises(UserError):
            move.action_include_vat_in_price()
            
        # Reset to draft
        move.state = 'draft'
        
        # Try to process with wrong move type (should fail)
        move.move_type = 'out_invoice'
        with self.assertRaises(UserError):
            move.action_include_vat_in_price()
            
        # Reset to correct move type
        move.move_type = 'in_invoice'
        
        # Process once
        move.invoice_line_ids[0].include_vat_cost = True
        move.action_include_vat_in_price()
        
        # Try to process again (should fail)
        with self.assertRaises(UserError):
            move.action_include_vat_in_price()
            
        # Try to restore with wrong move type (should fail)
        move.move_type = 'out_invoice'
        with self.assertRaises(UserError):
            move.action_restore_vat()
