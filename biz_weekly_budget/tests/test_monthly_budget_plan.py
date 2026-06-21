from odoo.tests import common
from odoo.exceptions import UserError, ValidationError
from odoo import fields


class TestMonthlyBudgetPlan(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency = cls.company.currency_id

        cls.department = cls.env['hr.department'].create({
            'name': 'Budget Test Dept',
        })

        cls.department2 = cls.env['hr.department'].create({
            'name': 'Budget Test Dept 2',
        })

    def _create_plan(self, month=None, year=None, total_budget=100000.0):
        return self.env['monthly.budget.plan'].create({
            'month': month or str(fields.Date.today().month).zfill(2),
            'year': year or str(fields.Date.today().year),
            'total_budget': total_budget,
            'company_id': self.company.id,
        })

    def _create_allocation(self, plan, department, percentage):
        return self.env['monthly.budget.allocation'].create({
            'plan_id': plan.id,
            'department_id': department.id if department else False,
            'percentage': percentage,
        })

    def test_plan_creation_defaults(self):
        plan = self._create_plan()
        self.assertEqual(plan.state, 'draft')
        self.assertTrue(plan.name)
        self.assertTrue(plan.date_from)
        self.assertTrue(plan.date_to)
        self.assertEqual(plan.total_budget, 100000.0)
        self.assertEqual(plan.company_id, self.company)
        self.assertFalse(plan.all_companies)

    def test_plan_name_sequence(self):
        plan = self._create_plan()
        self.assertNotEqual(plan.name, 'New')

    def test_plan_date_computation(self):
        plan = self.env['monthly.budget.plan'].create({
            'month': '06',
            'year': '2025',
            'total_budget': 100000.0,
            'company_id': self.company.id,
        })
        self.assertEqual(plan.date_from.month, 6)
        self.assertEqual(plan.date_from.year, 2025)
        self.assertEqual(plan.date_from.day, 1)
        self.assertEqual(plan.date_to.month, 6)
        self.assertEqual(plan.date_to.year, 2025)
        self.assertEqual(plan.date_to.day, 30)

    def test_plan_date_computation_december(self):
        plan = self.env['monthly.budget.plan'].create({
            'month': '12',
            'year': '2025',
            'total_budget': 100000.0,
            'company_id': self.company.id,
        })
        self.assertEqual(plan.date_from.month, 12)
        self.assertEqual(plan.date_from.day, 1)
        self.assertEqual(plan.date_to.month, 12)
        self.assertEqual(plan.date_to.day, 31)
        self.assertEqual(plan.date_to.year, 2025)

    def test_plan_missing_company_raises(self):
        with self.assertRaises(ValidationError):
            self.env['monthly.budget.plan'].create({
                'month': str(fields.Date.today().month).zfill(2),
                'year': str(fields.Date.today().year),
                'total_budget': 100000.0,
                'all_companies': False,
                'company_id': False,
            })

    def test_all_companies_clears_company_on_change(self):
        plan = self._create_plan()
        plan.all_companies = True
        plan._onchange_all_companies()
        self.assertFalse(plan.company_id)

    def test_confirm_empty_allocation_raises(self):
        plan = self._create_plan()
        with self.assertRaises(UserError):
            plan.action_confirm()

    def test_confirm_allocation_sum_mismatch_raises(self):
        plan = self._create_plan(total_budget=100000.0)
        self._create_allocation(plan, self.department, 50.0)
        self._create_allocation(plan, self.department2, 30.0)
        with self.assertRaises(UserError):
            plan.action_confirm()

    def test_confirm_allocation_sum_matches(self):
        plan = self._create_plan(total_budget=100000.0)
        self._create_allocation(plan, self.department, 60.0)
        self._create_allocation(plan, self.department2, 40.0)
        plan.action_confirm()
        self.assertEqual(plan.state, 'confirmed')

    def test_state_machine_full_cycle(self):
        plan = self._create_plan(total_budget=100000.0)
        self._create_allocation(plan, self.department, 100.0)
        plan.action_confirm()
        self.assertEqual(plan.state, 'confirmed')
        plan.action_done()
        self.assertEqual(plan.state, 'done')
        plan.action_cancel()
        self.assertEqual(plan.state, 'cancelled')
        plan.action_reset_draft()
        self.assertEqual(plan.state, 'draft')

    def test_confirm_department_budget_correct(self):
        plan = self._create_plan(total_budget=100000.0)
        alloc1 = self._create_allocation(plan, self.department, 70.0)
        alloc2 = self._create_allocation(plan, self.department2, 30.0)
        self.assertEqual(alloc1.amount, 70000.0)
        self.assertEqual(alloc2.amount, 30000.0)

    def test_total_budget_computed_from_allocations(self):
        plan = self._create_plan(total_budget=200000.0)
        self._create_allocation(plan, self.department, 50.0)
        self._create_allocation(plan, self.department2, 50.0)
        plan.action_confirm()
        self.assertAlmostEqual(plan.total_remaining, plan.total_budget)
        self.assertAlmostEqual(plan.total_used, 0.0)
        self.assertAlmostEqual(plan.total_reserved, 0.0)

    def test_duplicate_department_allocation_raises(self):
        plan = self._create_plan(total_budget=100000.0)
        self._create_allocation(plan, self.department, 50.0)
        with self.assertRaises(ValidationError):
            self._create_allocation(plan, self.department, 30.0)

    def test_only_one_null_department_allocation(self):
        plan = self._create_plan(total_budget=100000.0)
        self._create_allocation(plan, False, 50.0)
        with self.assertRaises(ValidationError):
            self._create_allocation(plan, False, 50.0)

    def test_percentage_out_of_range_raises(self):
        plan = self._create_plan(total_budget=100000.0)
        with self.assertRaises(ValidationError):
            self._create_allocation(plan, self.department, 150.0)

    def test_negative_percentage_raises(self):
        plan = self._create_plan(total_budget=100000.0)
        with self.assertRaises(ValidationError):
            self._create_allocation(plan, self.department, -10.0)
