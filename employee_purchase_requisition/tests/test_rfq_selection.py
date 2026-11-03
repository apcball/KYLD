from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRfqSelection(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vendor = cls.env['res.partner'].create({'name': 'PR RFQ Vendor'})
        cls.prod_a = cls.env['product.product'].create({'name': 'PR Prod A'})
        cls.prod_b = cls.env['product.product'].create({'name': 'PR Prod B'})
        cls.dept = cls.env['hr.department'].create({'name': 'PR RFQ Dept'})
        cls.employee = cls.env['hr.employee'].create({
            'name': 'PR RFQ Employee', 'department_id': cls.dept.id})
        cls.pr = cls.env['employee.purchase.requisition'].create({
            'employee_id': cls.employee.id,
            'user_id': cls.env.user.id,
            'department_id': cls.dept.id,
            'state': 'approved',
            'requisition_order_ids': [
                (0, 0, {'product_id': cls.prod_a.id, 'quantity': 5,
                        'unit_price': 10, 'partner_id': cls.vendor.id}),
                (0, 0, {'product_id': cls.prod_b.id, 'quantity': 3,
                        'unit_price': 20, 'partner_id': cls.vendor.id}),
            ],
        })
        cls.line_a, cls.line_b = cls.pr.requisition_order_ids

    def test_requires_selection(self):
        with self.assertRaises(ValidationError):
            self.pr.action_create_purchase_order()

    def test_requires_vendor(self):
        self.line_a.write({'partner_id': False, 'select_for_rfq': True})
        with self.assertRaises(ValidationError):
            self.pr.action_create_purchase_order()

    def test_partial_then_full(self):
        self.line_a.select_for_rfq = True
        self.pr.action_create_purchase_order()
        self.assertEqual(self.pr.state, 'approved')
        self.assertFalse(self.line_a.select_for_rfq)
        self.assertEqual(self.line_a.rfq_remaining_qty, 0)
        self.assertEqual(self.line_b.rfq_remaining_qty, 3)
        self.line_b.select_for_rfq = True
        self.pr.action_create_purchase_order()
        self.assertEqual(self.pr.state, 'purchase_order_created')

    def test_cancelled_po_restores_remaining(self):
        self.line_a.select_for_rfq = True
        self.pr.action_create_purchase_order()
        po = self.env['purchase.order'].search(
            [('requisition_order', '=', self.pr.name)])
        po.button_cancel()
        self.line_a.invalidate_recordset()
        self.assertEqual(self.line_a.rfq_remaining_qty, 5)
