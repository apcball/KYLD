from odoo.tests import common
from odoo.exceptions import UserError
from odoo import fields


class TestBudgetCheck(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency = cls.company.currency_id

        cls.department = cls.env['hr.department'].create({
            'name': 'Budget Check Dept',
        })

        cls.product = cls.env['product.product'].create({
            'name': 'Budget Check Product',
            'type': 'consu',
            'standard_price': 100.0,
        })

        cls.vendor = cls.env['res.partner'].create({
            'name': 'Budget Check Vendor',
            'supplier_rank': 1,
        })

        cls.user = cls.env['res.users'].create({
            'name': 'Budget Check User',
            'login': 'budget_check_user',
            'email': 'budget_check@test.com',
        })

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Budget Check Employee',
            'department_id': cls.department.id,
            'user_id': cls.user.id,
        })

        cls.plan = cls.env['monthly.budget.plan'].create({
            'month': str(fields.Date.today().month).zfill(2),
            'year': str(fields.Date.today().year),
            'total_budget': 10000.0,
            'company_id': cls.company.id,
        })
        cls.allocation = cls.env['monthly.budget.allocation'].create({
            'plan_id': cls.plan.id,
            'department_id': cls.department.id,
            'percentage': 100.0,
        })
        cls.plan.action_confirm()

    def _create_po(self, amount=5000.0, state='draft'):
        po = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'department_id': self.department.id,
            'payment_date': fields.Date.today(),
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': 'Test PO Line',
                'product_qty': 1,
                'price_unit': amount,
                'date_planned': fields.Date.today(),
                'department_id': self.department.id,
            })],
        })
        if state == 'purchase':
            po.approval_state = 'approved'
            po.button_confirm()
        return po

    def _assert_alloc_found(self, po):
        month_amounts = po._get_monthly_budget_allocation_for_po()
        self.assertTrue(month_amounts, "No budget allocation found for PO")

    def test_allocation_found_for_po(self):
        po = self._create_po(amount=5000.0)
        self._assert_alloc_found(po)

    def test_budget_check_within_limit(self):
        po = self._create_po(amount=5000.0)
        self._assert_alloc_found(po)
        po._check_monthly_budget()

    def test_budget_check_exceeds_limit_hard_block(self):
        po = self._create_po(amount=15000.0)
        self._assert_alloc_found(po)
        with self.assertRaises(UserError):
            po._check_monthly_budget()

    def test_budget_check_no_plan_raises(self):
        far_future = '2099-06-15'
        po = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'department_id': self.department.id,
            'payment_date': far_future,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': 'Test PO Line',
                'product_qty': 1,
                'price_unit': 1000.0,
                'date_planned': fields.Date.today(),
            })],
        })
        with self.assertRaises(UserError):
            po._check_monthly_budget()

    def test_po_budget_warning_flag_within_limit(self):
        po = self._create_po(amount=5000.0)
        self._assert_alloc_found(po)
        self.assertFalse(po.budget_warning)

    def test_budget_check_result_not_empty(self):
        po = self._create_po(amount=3000.0)
        self._assert_alloc_found(po)
        self.assertTrue(po.budget_check_result)

    def test_po_budget_reserved_flag(self):
        po = self._create_po(amount=5000.0)
        self._assert_alloc_found(po)
        po.write({'state': 'purchase'})
        po._update_budget_moves()
        po.invalidate_recordset(['is_budget_reserved'])
        self.assertTrue(po.is_budget_reserved)

    def test_po_clear_reserved_on_cancel(self):
        po = self._create_po(amount=5000.0)
        self._assert_alloc_found(po)
        po.write({'state': 'purchase'})
        po._update_budget_moves()
        po.button_cancel()
        po.invalidate_recordset(['is_budget_reserved'])
        self.assertFalse(po.is_budget_reserved)

    def test_check_monthly_budget_within_limit_after_state_change(self):
        po = self._create_po(amount=8000.0)
        self._assert_alloc_found(po)
        po.approval_state = 'approved'
        po.button_confirm()
        self.assertEqual(po.state, 'purchase')

    def test_check_monthly_budget_exceeds_after_state_change_block(self):
        po = self._create_po(amount=12000.0)
        self._assert_alloc_found(po)
        with self.assertRaises(UserError):
            po.button_confirm()

    def test_remaining_to_bill_computation(self):
        po = self._create_po(amount=5000.0)
        self._assert_alloc_found(po)
        po.write({'state': 'purchase'})
        self.assertAlmostEqual(po.remaining_to_bill, 5000.0)

    def test_source_doc_reservation_reuse(self):
        po = self._create_po(amount=5000.0)
        self.assertFalse(po._has_source_budget_reservation())

    def test_budget_check_passes_with_approved_request(self):
        po = self._create_po(amount=15000.0)
        self._assert_alloc_found(po)
        self.env['buz.budget.approval.request'].create({
            'document_type': 'po',
            'ref_po_id': po.id,
            'state': 'approved',
            'amount_limit': 10000.0,
            'amount_used': 0.0,
            'amount_reserved': 0.0,
            'amount_requested': 15000.0,
            'amount_overage': 5000.0,
        })
        po._check_monthly_budget()
