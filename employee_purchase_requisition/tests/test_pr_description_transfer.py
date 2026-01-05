# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestPRDescriptionTransfer(TransactionCase):
    """Test that description from PR is properly transferred to PO"""

    def setUp(self):
        super(TestPRDescriptionTransfer, self).setUp()
        
        # Create test data
        self.employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
        })
        
        self.product = self.env['product.product'].create({
            'name': 'Test Product',
            'type': 'product',
        })
        
        self.vendor = self.env['res.partner'].create({
            'name': 'Test Vendor',
            'supplier_rank': 1,
        })
        
        self.user = self.env['res.users'].create({
            'name': 'Test User',
            'login': 'testuser',
            'email': 'test@test.com',
        })

    def test_description_transfer_with_description_only(self):
        """Test that description is transferred when only description is set"""
        # Create PR with description
        pr = self.env['employee.purchase.requisition'].create({
            'employee_id': self.employee.id,
            'user_id': self.user.id,
            'requisition_date': '2024-01-01',
        })
        
        # Create PR line with custom description
        pr_line = self.env['requisition.order'].create({
            'requisition_product_id': pr.id,
            'product_id': self.product.id,
            'description': 'Custom description for this product',
            'quantity': 10,
            'unit_price': 100,
            'partner_id': self.vendor.id,
        })
        
        # Create PO from PR
        pr.action_create_purchase_order()
        
        # Find created PO
        po = self.env['purchase.order'].search([('requisition_order', '=', pr.name)])
        
        # Verify description was transferred
        self.assertEqual(len(po), 1, "One PO should be created")
        self.assertEqual(len(po.order_line), 1, "One PO line should be created")
        self.assertEqual(
            po.order_line[0].name,
            'Custom description for this product',
            "Description should be transferred to PO line"
        )

    def test_description_transfer_with_description_and_remark(self):
        """Test that both description and remark are transferred"""
        # Create PR with description and remark
        pr = self.env['employee.purchase.requisition'].create({
            'employee_id': self.employee.id,
            'user_id': self.user.id,
            'requisition_date': '2024-01-01',
        })
        
        # Create PR line with description and remark
        pr_line = self.env['requisition.order'].create({
            'requisition_product_id': pr.id,
            'product_id': self.product.id,
            'description': 'Custom description',
            'remark': 'Important: Handle with care',
            'quantity': 5,
            'unit_price': 200,
            'partner_id': self.vendor.id,
        })
        
        # Create PO from PR
        pr.action_create_purchase_order()
        
        # Find created PO
        po = self.env['purchase.order'].search([('requisition_order', '=', pr.name)])
        
        # Verify description and remark were transferred
        expected_text = "Custom description\nImportant: Handle with care"
        self.assertEqual(
            po.order_line[0].name,
            expected_text,
            "Both description and remark should be transferred to PO line"
        )

    def test_description_fallback_to_product_name(self):
        """Test that product name is used when description is not set"""
        # Create PR without description
        pr = self.env['employee.purchase.requisition'].create({
            'employee_id': self.employee.id,
            'user_id': self.user.id,
            'requisition_date': '2024-01-01',
        })
        
        # Create PR line without description
        pr_line = self.env['requisition.order'].create({
            'requisition_product_id': pr.id,
            'product_id': self.product.id,
            'quantity': 3,
            'unit_price': 150,
            'partner_id': self.vendor.id,
        })
        
        # Create PO from PR
        pr.action_create_purchase_order()
        
        # Find created PO
        po = self.env['purchase.order'].search([('requisition_order', '=', pr.name)])
        
        # Verify product name was used as fallback
        self.assertEqual(
            po.order_line[0].name,
            'Test Product',
            "Product name should be used when description is empty"
        )

    def test_description_with_remark_only(self):
        """Test that remark is appended even when using product name"""
        # Create PR with remark but no description
        pr = self.env['employee.purchase.requisition'].create({
            'employee_id': self.employee.id,
            'user_id': self.user.id,
            'requisition_date': '2024-01-01',
        })
        
        # Create PR line with remark only
        pr_line = self.env['requisition.order'].create({
            'requisition_product_id': pr.id,
            'product_id': self.product.id,
            'remark': 'Urgent order',
            'quantity': 7,
            'unit_price': 180,
            'partner_id': self.vendor.id,
        })
        
        # Create PO from PR
        pr.action_create_purchase_order()
        
        # Find created PO
        po = self.env['purchase.order'].search([('requisition_order', '=', pr.name)])
        
        # Verify product name + remark
        expected_text = "Test Product\nUrgent order"
        self.assertEqual(
            po.order_line[0].name,
            expected_text,
            "Product name and remark should both be in PO line"
        )
