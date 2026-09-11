from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged('post_install', '-at_install')
class TestExecutiveDashboard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = new_test_user(
            cls.env, login='cost_dashboard_manager',
            groups='job_costing_management.group_job_costing_manager',
            company_id=cls.env.company.id,
        )
        cls.project = cls.env['project.project'].create({
            'name': 'Executive dashboard', 'company_id': cls.env.company.id,
        })
        cls.sheet = cls.env['job.cost.sheet'].create({
            'project_id': cls.project.id, 'state': 'approved',
            'currency_id': cls.env.company.currency_id.id,
            'date_start': '2026-01-15',
            'material_cost_ids': [fields.Command.create({
                'name': 'Baseline', 'cost_type': 'material',
                'boq_qty': 10, 'boq_unit_cost': 100,
            })],
        })

    def dashboard(self, **filters):
        return self.env['job.cost.sheet'].with_user(self.manager).get_executive_dashboard(
            dict(project_id=self.project.id, **filters))

    def test_budget_actual_and_drilldown(self):
        # Seed stored snapshot amounts: dashboard must reproduce the Cost Sheet,
        # independently of procurement/timesheet computation tested elsewhere.
        self.sheet.write({'actual_total_cost': 1100, 'actual_material_cost': 1100})
        data = self.dashboard()
        group = data['groups'][0]
        self.assertEqual(group['budget'], 1000)
        self.assertEqual(group['actual'], 1100)
        self.assertEqual(group['remaining'], -100)
        self.assertAlmostEqual(group['ratio'], 110)
        self.assertEqual(group['over_ids'], self.sheet.ids)
        self.assertEqual(data['attention'][0]['status'], 'over')
        self.assertEqual(group['categories'][0]['actual'], 1100)
        self.assertEqual(self.env['job.cost.sheet'].search(data['domain']), self.sheet)

    def test_missing_budget_is_separate(self):
        self.sheet.currency_id = False
        self.sheet.material_cost_ids.boq_qty = 0
        self.sheet.write({'actual_total_cost': 300})
        group = self.dashboard()['groups'][0]
        self.assertEqual(group['actual'], 300)
        self.assertEqual(group['comparable_actual'], 0)
        self.assertEqual(group['unbudgeted_actual'], 300)
        self.assertEqual(group['unbudgeted_count'], 1)
        self.assertIsNone(group['ratio'])
        self.assertEqual(group['fallback_count'], 1)

    def test_threshold_and_negative_actual(self):
        for actual, status in [(900, 'near'), (1000, 'near'), (1001, 'over')]:
            self.sheet.actual_total_cost = actual
            self.assertEqual(self.dashboard()['attention'][0]['status'], status)
        self.sheet.actual_total_cost = -50
        result = self.dashboard()
        self.assertFalse(result['attention'])
        self.assertEqual(result['groups'][0]['remaining'], 1050)

    def test_filters(self):
        self.assertFalse(self.dashboard(date_from='2026-02-01')['groups'])
        self.assertTrue(self.dashboard(date_from='2026-01-15', date_to='2026-01-15')['groups'])
        self.sheet.state = 'done'
        self.assertFalse(self.dashboard()['groups'])
        self.assertTrue(self.dashboard(states=['done'])['groups'])
        with self.assertRaises(ValidationError):
            self.dashboard(states=[])
        with self.assertRaises(ValidationError):
            self.dashboard(date_from='2026-02-01', date_to='2026-01-01')

    def test_currency_and_multiple_sheets(self):
        currency = self.env['res.currency'].with_context(active_test=False).search(
            [('id', '!=', self.env.company.currency_id.id)], limit=1)
        currency.active = True
        other = self.sheet.copy({'currency_id': currency.id, 'state': 'approved'})
        data = self.dashboard()
        self.assertEqual(len(data['groups']), 2)
        self.assertEqual(sum(g['count'] for g in data['groups']), 2)
        other.currency_id = self.env.company.currency_id
        data = self.dashboard()
        self.assertEqual(len(data['groups']), 1)
        self.assertEqual(data['groups'][0]['projects'][0]['count'], 2)

    def test_access_and_company(self):
        user = new_test_user(self.env, login='cost_dashboard_regular',
                             groups='job_costing_management.group_job_costing_user')
        with self.assertRaises(AccessError):
            self.env['job.cost.sheet'].with_user(user).get_executive_dashboard()
        company = self.env['res.company'].create({'name': 'Restricted dashboard company'})
        with self.assertRaises(AccessError):
            self.dashboard(company_id=company.id)

    def test_attention_pagination(self):
        self.sheet.actual_total_cost = 1100
        for index in range(21):
            self.env['job.cost.sheet'].create({
                'project_id': self.project.id, 'state': 'approved',
            })
        model = self.env['job.cost.sheet'].with_user(self.manager)
        first = model.get_executive_dashboard({'project_id': self.project.id})
        second = model.get_executive_dashboard({'project_id': self.project.id}, page=1)
        self.assertEqual(len(first['attention']), 20)
        self.assertEqual(len(second['attention']), 2)
        self.assertFalse(set(r['id'] for r in first['attention']) &
                         set(r['id'] for r in second['attention']))

    def test_record_rules_are_respected(self):
        self.env['ir.rule'].create({
            'name': 'Hide dashboard fixture',
            'model_id': self.env['ir.model']._get_id('job.cost.sheet'),
            'domain_force': "[('id', '!=', %d)]" % self.sheet.id,
        })
        result = self.dashboard()
        self.assertFalse(result['groups'])
        self.assertFalse(result['projects'])
        self.assertFalse(result['attention'])

    def test_category_totals(self):
        for kind, budget, actual in [('labour', 500, 250), ('overhead', 300, 100)]:
            self.env['job.cost.line'].create({
                'cost_sheet_id': self.sheet.id, 'cost_type': kind,
                'name': kind, 'boq_qty': 1, 'boq_unit_cost': budget,
            })
        self.env.flush_all()
        self.sheet.write({'actual_total_cost': 350, 'actual_labour_cost': 250,
                          'actual_overhead_cost': 100})
        group = self.dashboard()['groups'][0]
        self.assertEqual(group['budget'], 1800)
        self.assertEqual(sum(c['budget'] for c in group['categories']), 1800)
        self.assertEqual(sum(c['actual'] for c in group['categories']), 350)
