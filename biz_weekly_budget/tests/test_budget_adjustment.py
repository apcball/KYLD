from odoo.tests import common
from odoo.exceptions import UserError, ValidationError
from odoo import fields


class TestBudgetAdjustment(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.department = cls.env['hr.department'].create({
            'name': 'Adjustment Test Dept',
        })

        cls.plan = cls.env['monthly.budget.plan'].create({
            'month': str(fields.Date.today().month).zfill(2),
            'year': str(fields.Date.today().year),
            'total_budget': 100000.0,
            'company_id': cls.company.id,
        })
        cls.allocation = cls.env['monthly.budget.allocation'].create({
            'plan_id': cls.plan.id,
            'department_id': cls.department.id,
            'percentage': 100.0,
        })
        cls.plan.action_confirm()

    def test_wizard_creation(self):
        wizard = self.env['budget.adjustment.wizard'].create({
            'monthly_allocation_id': self.allocation.id,
            'current_amount': self.allocation.amount,
            'new_amount': 60000.0,
            'reason': 'Budget reallocation for Q2',
        })
        self.assertEqual(wizard.monthly_allocation_id, self.allocation)
        self.assertEqual(wizard.new_amount, 60000.0)

    def test_adjust_budget_increase(self):
        old_amount = self.allocation.amount
        wizard = self.env['budget.adjustment.wizard'].create({
            'monthly_allocation_id': self.allocation.id,
            'current_amount': self.allocation.amount,
            'new_amount': old_amount + 50000.0,
            'reason': 'Additional funds approved',
        })
        wizard.action_confirm()
        self.allocation.invalidate_recordset(['amount'])
        self.assertAlmostEqual(self.allocation.amount, old_amount + 50000.0)

    def test_adjust_budget_decrease(self):
        old_amount = self.allocation.amount
        wizard = self.env['budget.adjustment.wizard'].create({
            'monthly_allocation_id': self.allocation.id,
            'current_amount': self.allocation.amount,
            'new_amount': old_amount - 20000.0,
            'reason': 'Cost reduction initiative',
        })
        wizard.action_confirm()
        self.allocation.invalidate_recordset(['amount'])
        self.assertAlmostEqual(self.allocation.amount, old_amount - 20000.0)

    def test_adjust_without_reason_raises(self):
        with self.assertRaises(ValidationError):
            self.env['budget.adjustment.wizard'].create({
                'monthly_allocation_id': self.allocation.id,
                'current_amount': self.allocation.amount,
                'new_amount': 50000.0,
                'reason': False,
            })

    def test_negative_amount_raises(self):
        wizard = self.env['budget.adjustment.wizard'].create({
            'monthly_allocation_id': self.allocation.id,
            'current_amount': self.allocation.amount,
            'new_amount': -1000.0,
            'reason': 'Negative test',
        })
        with self.assertRaises(UserError):
            wizard.action_confirm()

    def test_action_confirm_returns_close(self):
        wizard = self.env['budget.adjustment.wizard'].create({
            'monthly_allocation_id': self.allocation.id,
            'current_amount': self.allocation.amount,
            'new_amount': self.allocation.amount,
            'reason': 'No change test',
        })
        result = wizard.action_confirm()
        self.assertEqual(result['type'], 'ir.actions.act_window_close')

    def test_allocation_adjust_action(self):
        result = self.allocation.action_adjust_budget()
        self.assertEqual(result['res_model'], 'budget.adjustment.wizard')
        self.assertEqual(result['context']['default_monthly_allocation_id'], self.allocation.id)
