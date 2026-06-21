from odoo.tests import common
from odoo import fields


class TestBudgetMove(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency = cls.company.currency_id

        cls.department = cls.env['hr.department'].create({
            'name': 'Budget Move Dept',
        })
        cls.analytic_plan = cls.env['account.analytic.plan'].create({
            'name': 'Test Analytic Plan',
        })
        cls.analytic_account = cls.env['account.analytic.account'].create({
            'name': 'Test Analytic',
            'plan_id': cls.analytic_plan.id,
        })

        cls.product = cls.env['product.product'].create({
            'name': 'Budget Test Product',
            'type': 'consu',
            'standard_price': 100.0,
        })

        cls.vendor = cls.env['res.partner'].create({
            'name': 'Budget Vendor',
            'supplier_rank': 1,
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

    def _create_budget_move(self, amount=1000.0, move_type='reserved'):
        return self.env['budget.move'].create({
            'name': 'Test Move',
            'allocation_id': self.allocation.id,
            'source_model': 'purchase.order',
            'source_id': 9999,
            'source_line_id': 0,
            'analytic_account_id': self.analytic_account.id,
            'department_id': self.department.id,
            'amount': amount,
            'move_type': move_type,
            'date': fields.Date.today(),
        })

    def test_budget_move_creation(self):
        move = self._create_budget_move()
        self.assertTrue(move.name)
        self.assertEqual(move.allocation_id, self.allocation)
        self.assertEqual(move.plan_id, self.plan)
        self.assertEqual(move.move_type, 'reserved')
        self.assertEqual(move.amount, 1000.0)
        self.assertTrue(move.date)

    def test_budget_move_month_key(self):
        move = self._create_budget_move()
        expected_key = fields.Date.today().strftime('%Y-%m')
        self.assertEqual(move.month_key, expected_key)

    def test_budget_move_week_key(self):
        move = self._create_budget_move()
        expected_key = fields.Date.today().strftime('%Y-W%W')
        self.assertEqual(move.week_key, expected_key)

    def test_aging_days_non_reserved(self):
        move = self._create_budget_move(move_type='used')
        self.assertEqual(move.aging_days, 0)

    def test_aging_days_reserved(self):
        move = self._create_budget_move(move_type='reserved')
        self.assertGreaterEqual(move.aging_days, 0)

    def test_budget_move_increases_used(self):
        self._create_budget_move(amount=5000.0, move_type='used')
        self.assertAlmostEqual(self.allocation.amount_used, 5000.0)

    def test_budget_move_increases_reserved(self):
        self._create_budget_move(amount=3000.0, move_type='reserved')
        self.assertAlmostEqual(self.allocation.amount_reserved, 3000.0)

    def test_budget_move_increases_forecast(self):
        self._create_budget_move(amount=2000.0, move_type='forecast')
        self.assertAlmostEqual(self.allocation.forecast_amount, 2000.0)

    def test_budget_move_multi_type_sum(self):
        self._create_budget_move(amount=1000.0, move_type='used')
        self._create_budget_move(amount=2000.0, move_type='reserved')
        self._create_budget_move(amount=3000.0, move_type='forecast')
        self.assertAlmostEqual(self.allocation.amount_used, 1000.0)
        self.assertAlmostEqual(self.allocation.amount_reserved, 2000.0)
        self.assertAlmostEqual(self.allocation.forecast_amount, 3000.0)

    def test_extract_analytic_distribution_on_po_line(self):
        po = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': 'Test Line',
                'product_qty': 10,
                'price_unit': 100.0,
                'date_planned': fields.Date.today(),
            })],
        })
        line = po.order_line[0]
        dists = self.env['budget.move'].extract_analytic_distribution(line)
        self.assertTrue(dists)
        self.assertEqual(len(dists), 1)
        self.assertAlmostEqual(dists[0]['percentage'], 1.0)

    def test_budget_move_company_fallback(self):
        move = self._create_budget_move()
        self.assertTrue(move.company_id)

    def test_budget_move_currency_related(self):
        move = self._create_budget_move()
        self.assertEqual(move.currency_id, self.company.currency_id)

    def test_action_release_aged_reservations(self):
        self._create_budget_move(amount=1000.0, move_type='reserved')
        self.env['budget.move'].action_release_aged_reservations()
        self.assertLessEqual(
            len(self.env['budget.move'].search([
                ('move_type', '=', 'reserved'),
                ('allocation_id', '=', self.allocation.id),
            ])),
            1
        )
