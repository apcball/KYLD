from odoo.tests import common
from odoo import fields


class TestBudgetAllocation(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency = cls.company.currency_id

        cls.department = cls.env['hr.department'].create({
            'name': 'Alloc Test Dept',
        })
        cls.department2 = cls.env['hr.department'].create({
            'name': 'Alloc Test Dept 2',
        })
        cls.department3 = cls.env['hr.department'].create({
            'name': 'Alloc Test Dept 3',
        })

        cls.plan = cls.env['monthly.budget.plan'].create({
            'month': str(fields.Date.today().month).zfill(2),
            'year': str(fields.Date.today().year),
            'total_budget': 200000.0,
            'company_id': cls.company.id,
        })
        cls.alloc_dept1 = cls.env['monthly.budget.allocation'].create({
            'plan_id': cls.plan.id,
            'department_id': cls.department.id,
            'percentage': 50.0,
        })
        cls.alloc_dept2 = cls.env['monthly.budget.allocation'].create({
            'plan_id': cls.plan.id,
            'department_id': cls.department2.id,
            'percentage': 30.0,
        })
        cls.alloc_base = cls.env['monthly.budget.allocation'].create({
            'plan_id': cls.plan.id,
            'department_id': False,
            'percentage': 20.0,
        })
        cls.plan.action_confirm()

    def test_allocation_amounts(self):
        self.assertAlmostEqual(self.alloc_dept1.amount, 100000.0)
        self.assertAlmostEqual(self.alloc_dept2.amount, 60000.0)
        self.assertAlmostEqual(self.alloc_base.amount, 40000.0)

    def test_initial_remaining(self):
        self.assertAlmostEqual(self.alloc_dept1.amount_remaining, 100000.0)
        self.assertAlmostEqual(self.alloc_dept2.amount_available, 60000.0)
        self.assertAlmostEqual(self.alloc_dept1.status, 'normal')

    def test_related_fields(self):
        self.assertEqual(self.alloc_dept1.plan_id, self.plan)
        self.assertEqual(self.alloc_dept1.company_id, self.company)
        self.assertEqual(self.alloc_dept1.plan_state, 'confirmed')
        self.assertEqual(self.alloc_dept1.date_from, self.plan.date_from)
        self.assertEqual(self.alloc_dept1.date_to, self.plan.date_to)

    def test_get_allocation_priority1_same_company_same_department(self):
        alloc = self.env['monthly.budget.allocation']._get_allocation(
            self.plan.date_from, self.department, self.company
        )
        self.assertEqual(alloc, self.alloc_dept1)

    def test_get_allocation_priority2_same_company_no_department(self):
        alloc = self.env['monthly.budget.allocation']._get_allocation(
            self.plan.date_from, False, self.company
        )
        self.assertEqual(alloc, self.alloc_base)

    def test_get_allocation_priority3_global_company_same_department_name(self):
        global_plan = self.env['monthly.budget.plan'].create({
            'month': str(fields.Date.today().month).zfill(2),
            'year': str(fields.Date.today().year),
            'total_budget': 50000.0,
            'all_companies': True,
            'company_id': False,
        })
        global_alloc = self.env['monthly.budget.allocation'].create({
            'plan_id': global_plan.id,
            'department_id': self.department3.id,
            'percentage': 100.0,
        })
        global_plan.action_confirm()

        other_company = self.env['res.company'].create({
            'name': 'Other Co',
        })
        alloc = self.env['monthly.budget.allocation']._get_allocation(
            global_plan.date_from, self.department3, other_company
        )
        self.assertEqual(alloc, global_alloc)

    def test_get_allocation_no_plan_found(self):
        far_date = fields.Date.from_string('2099-01-15')
        alloc = self.env['monthly.budget.allocation']._get_allocation(
            far_date, self.department, self.company
        )
        self.assertFalse(alloc)

    def test_get_allocation_empty_target_date(self):
        alloc = self.env['monthly.budget.allocation']._get_allocation(
            False, self.department, self.company
        )
        self.assertFalse(alloc)

    def test_allocation_status_normal_when_under_budget(self):
        self.assertEqual(self.alloc_dept1.status, 'normal')
        self.assertFalse(self.alloc_dept1.usage_percentage > 0)

    def test_allocation_amount_available_formula(self):
        self.assertAlmostEqual(
            self.alloc_dept1.amount_available,
            self.alloc_dept1.amount - self.alloc_dept1.amount_used - self.alloc_dept1.amount_reserved
        )

    def test_forecast_available_includes_used_and_reserved(self):
        BudgetMove = self.env['budget.move'].sudo()
        common_vals = {
            'allocation_id': self.alloc_dept1.id,
            'source_model': 'purchase.order',
            'source_id': 0,
            'date': fields.Date.today(),
        }
        BudgetMove.create({
            **common_vals,
            'name': 'Reserved',
            'amount': 1000.0,
            'move_type': 'reserved',
        })
        BudgetMove.create({
            **common_vals,
            'name': 'Forecast',
            'amount': 2000.0,
            'move_type': 'forecast',
        })
        self.assertAlmostEqual(
            self.alloc_dept1.amount_available_forecast,
            self.alloc_dept1.amount - 1000.0 - 2000.0,
        )

    def test_zero_budget_no_division_error(self):
        plan = self.env['monthly.budget.plan'].create({
            'month': str(fields.Date.today().month).zfill(2),
            'year': str(fields.Date.today().year),
            'total_budget': 0.0,
            'company_id': self.company.id,
        })
        alloc = self.env['monthly.budget.allocation'].create({
            'plan_id': plan.id,
            'department_id': self.department.id,
            'percentage': 100.0,
        })
        self.assertEqual(alloc.usage_percentage, 0.0)

    def test_exceeded_status(self):
        BudgetMove = self.env['budget.move'].sudo()
        BudgetMove.create({
            'name': 'Test Used',
            'allocation_id': self.alloc_dept1.id,
            'source_model': 'account.move',
            'source_id': 0,
            'amount': self.alloc_dept1.amount + 1,
            'move_type': 'used',
            'date': fields.Date.today(),
        })
        self.assertEqual(self.alloc_dept1.status, 'exceeded')

    def test_reserved_amount_can_set_exceeded_status(self):
        self.env['budget.move'].sudo().create({
            'name': 'Reserved over limit',
            'allocation_id': self.alloc_dept1.id,
            'source_model': 'purchase.order',
            'source_id': 0,
            'amount': self.alloc_dept1.amount + 1,
            'move_type': 'reserved',
            'date': fields.Date.today(),
        })
        self.assertEqual(self.alloc_dept1.status, 'exceeded')
