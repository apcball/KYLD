from odoo.tests import common
from odoo.exceptions import UserError, ValidationError
from odoo import fields


class TestBudgetApproval(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency = cls.company.currency_id

        cls.department = cls.env['hr.department'].create({
            'name': 'Approval Test Dept',
        })

        cls.product = cls.env['product.product'].create({
            'name': 'Approval Product',
            'type': 'consu',
        })

        cls.vendor = cls.env['res.partner'].create({
            'name': 'Approval Vendor',
            'supplier_rank': 1,
        })

        cls.manager_user = cls.env['res.users'].create({
            'name': 'Budget Manager',
            'login': 'budget_manager',
            'email': 'manager@test.com',
            'groups_id': [
                fields.Command.link(
                    cls.env.ref('biz_weekly_budget.group_budget_manager').id
                ),
            ],
        })

        cls.plan = cls.env['monthly.budget.plan'].create({
            'month': str(fields.Date.today().month).zfill(2),
            'year': str(fields.Date.today().year),
            'total_budget': 50000.0,
            'company_id': cls.company.id,
        })
        cls.allocation = cls.env['monthly.budget.allocation'].create({
            'plan_id': cls.plan.id,
            'department_id': cls.department.id,
            'percentage': 100.0,
        })
        cls.plan.action_confirm()

    def test_create_approval_request(self):
        req = self.env['buz.budget.approval.request'].create({
            'document_type': 'po',
            'ref_po_id': 0,
            'budget_allocation_id': self.allocation.id,
            'amount_limit': 50000.0,
            'amount_used': 0.0,
            'amount_reserved': 0.0,
            'amount_requested': 60000.0,
            'amount_overage': 10000.0,
        })
        self.assertEqual(req.state, 'pending')
        self.assertTrue(req.name)
        self.assertEqual(req.requester_id, self.env.user)

    def test_approve_request(self):
        req = self.env['buz.budget.approval.request'].create({
            'document_type': 'po',
            'ref_po_id': 0,
            'budget_allocation_id': self.allocation.id,
            'amount_limit': 50000.0,
            'amount_used': 0.0,
            'amount_reserved': 0.0,
            'amount_requested': 60000.0,
            'amount_overage': 10000.0,
        })
        req = req.with_user(self.manager_user)
        req.note = 'Approved due to project urgency'
        req._do_approve()
        self.assertEqual(req.state, 'approved')
        self.assertEqual(req.approver_id, self.manager_user)

    def test_reject_request_requires_note(self):
        req = self.env['buz.budget.approval.request'].create({
            'document_type': 'po',
            'ref_po_id': 0,
            'budget_allocation_id': self.allocation.id,
            'amount_limit': 50000.0,
            'amount_used': 0.0,
            'amount_reserved': 0.0,
            'amount_requested': 60000.0,
            'amount_overage': 10000.0,
        })
        req = req.with_user(self.manager_user)
        with self.assertRaises(ValidationError):
            req._do_reject()

    def test_reject_request(self):
        req = self.env['buz.budget.approval.request'].create({
            'document_type': 'po',
            'ref_po_id': 0,
            'budget_allocation_id': self.allocation.id,
            'amount_limit': 50000.0,
            'amount_used': 0.0,
            'amount_reserved': 0.0,
            'amount_requested': 60000.0,
            'amount_overage': 10000.0,
        })
        req = req.with_user(self.manager_user)
        req.note = 'Budget exhausted for this period'
        req._do_reject()
        self.assertEqual(req.state, 'rejected')

    def test_cancel_request(self):
        req = self.env['buz.budget.approval.request'].create({
            'document_type': 'po',
            'ref_po_id': 0,
            'budget_allocation_id': self.allocation.id,
            'amount_limit': 50000.0,
            'amount_used': 0.0,
            'amount_reserved': 0.0,
            'amount_requested': 60000.0,
            'amount_overage': 10000.0,
        })
        req.action_cancel()
        self.assertEqual(req.state, 'cancelled')

    def test_cancel_non_pending_raises(self):
        req = self.env['buz.budget.approval.request'].create({
            'document_type': 'po',
            'ref_po_id': 0,
            'budget_allocation_id': self.allocation.id,
            'amount_limit': 50000.0,
            'amount_used': 0.0,
            'amount_reserved': 0.0,
            'amount_requested': 60000.0,
            'amount_overage': 10000.0,
        })
        req.note = 'Approved'
        req = req.with_user(self.manager_user)
        req._do_approve()
        with self.assertRaises(UserError):
            req.action_cancel()

    def test_get_or_create_pending_request_existing(self):
        first = self.env['buz.budget.approval.request']._get_or_create_pending_request(
            'po', 'ref_po_id', 42,
            self.allocation, 60000.0, 0.0, 0.0, 50000.0, 10000.0,
        )
        second = self.env['buz.budget.approval.request']._get_or_create_pending_request(
            'po', 'ref_po_id', 42,
            self.allocation, 60000.0, 0.0, 0.0, 50000.0, 10000.0,
        )
        self.assertEqual(first.id, second.id)

    def test_document_ref_computation_po(self):
        po = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
        })
        req = self.env['buz.budget.approval.request'].create({
            'document_type': 'po',
            'ref_po_id': po.id,
        })
        self.assertEqual(req.document_ref, po.name)

    def test_approve_non_manager_raises(self):
        req = self.env['buz.budget.approval.request'].create({
            'document_type': 'po',
            'ref_po_id': 0,
            'amount_limit': 50000.0,
            'amount_used': 0.0,
            'amount_reserved': 0.0,
            'amount_requested': 60000.0,
            'amount_overage': 10000.0,
        })
        with self.assertRaises(UserError):
            req.action_approve()

    def test_non_manager_cannot_call_private_approve(self):
        req = self.env['buz.budget.approval.request'].create({
            'document_type': 'po',
            'amount_requested': 60000.0,
        })
        with self.assertRaises(UserError):
            req._do_approve()

    def test_non_manager_cannot_approve_through_wizard_rpc(self):
        req = self.env['buz.budget.approval.request'].create({
            'document_type': 'po',
            'amount_requested': 60000.0,
        })
        wizard = self.env['budget.approval.reason.wizard'].create({
            'request_id': req.id,
            'action_type': 'approve',
            'note': 'Forged approval',
        })
        with self.assertRaises(UserError):
            wizard.action_confirm()

    def test_direct_state_write_is_blocked(self):
        req = self.env['buz.budget.approval.request'].create({
            'document_type': 'po',
            'amount_requested': 60000.0,
        })
        with self.assertRaises(UserError):
            req.write({'state': 'approved'})

    def test_create_cannot_forge_approved_state(self):
        req = self.env['buz.budget.approval.request'].create({
            'document_type': 'po',
            'amount_requested': 60000.0,
            'state': 'approved',
            'approver_id': self.manager_user.id,
        })
        self.assertEqual(req.state, 'pending')
        self.assertFalse(req.approver_id)

    def test_other_user_cannot_cancel_request(self):
        req = self.env['buz.budget.approval.request'].create({
            'document_type': 'po',
            'amount_requested': 60000.0,
        })
        with self.assertRaises(UserError):
            req.with_user(self.manager_user).action_cancel()

    def test_approve_non_pending_raises(self):
        req = self.env['buz.budget.approval.request'].create({
            'document_type': 'po',
            'ref_po_id': 0,
            'budget_allocation_id': self.allocation.id,
            'amount_limit': 50000.0,
            'amount_used': 0.0,
            'amount_reserved': 0.0,
            'amount_requested': 60000.0,
            'amount_overage': 10000.0,
        })
        req = req.with_user(self.manager_user)
        req.note = 'Approved'
        req._do_approve()
        with self.assertRaises(UserError):
            req.action_approve()
