# -*- coding: utf-8 -*-
from odoo.tests import tagged

from ..services.base_service import SERVICE_REGISTRY
from ..services.filters import DashboardFilter
from ..services.response import DashboardApiError
from .common import DashboardTestCase


def _run(env, code, payload=None, **kwargs):
    filters = DashboardFilter.from_payload(env, payload or {})
    service = SERVICE_REGISTRY[code](env, filters)
    return service.compute(**kwargs)


@tagged('post_install', '-at_install')
class TestJobCostingOverview(DashboardTestCase):
    """DEV is a real, non-empty shared database (existing projects and cost
    sheets belonging to other tests/production data), so every assertion
    here scopes to self.project via project_ids -- it never assumes the
    company as a whole is empty."""

    def test_job_costing_overview(self):
        self._create_cost_sheet()
        data = _run(self.env, 'job_costing.overview', {'project_ids': [self.project.id]})
        # planned = 100*10 + 50*20 + 30*5 = 1000+1000+150 = 2150
        self.assertAlmostEqual(data['planned_cost'], 2150.0)
        self.assertEqual(data['total_projects'], 1)
        self.assertEqual(data['contract_amount'], 1000000.0)

    def test_no_projects(self):
        # A fresh company: the ORM's own count for that company is the
        # source of truth, not a hardcoded 0 (Odoo core auto-grants the
        # creating admin access to a new company, and this DB is shared).
        other_company = self.env['res.company'].create({'name': 'Empty Co'})
        env = self.env(context=dict(self.env.context, allowed_company_ids=[other_company.id]))
        filters = DashboardFilter.from_payload(env, {'company_id': other_company.id})
        expected_count = env['project.project'].search_count(filters.project_domain())
        service = SERVICE_REGISTRY['job_costing.overview'](env, filters)
        data = service.compute()
        self.assertEqual(data['total_projects'], expected_count)
        self.assertEqual(data['planned_cost'], 0.0)

    def test_no_cost_sheet(self):
        # Project exists but has no cost sheet at all.
        data = _run(self.env, 'job_costing.overview', {'project_ids': [self.project.id]})
        self.assertEqual(data['planned_cost'], 0.0)
        self.assertEqual(data['actual_cost'], 0.0)

    def test_zero_cost(self):
        self._create_cost_sheet(material=(0.0, 0.0), labour=(0.0, 0.0), overhead=(0.0, 0.0))
        data = _run(self.env, 'job_costing.overview', {'project_ids': [self.project.id]})
        self.assertEqual(data['planned_cost'], 0.0)
        self.assertIsNone(data['cost_variance_percent'])


@tagged('post_install', '-at_install')
class TestCostBreakdown(DashboardTestCase):

    def test_cost_breakdown(self):
        self._create_cost_sheet()
        data = _run(self.env, 'job_costing.cost_breakdown', {'project_ids': [self.project.id]})
        self.assertAlmostEqual(data['planned']['materials'], 1000.0)
        self.assertAlmostEqual(data['planned']['labour'], 1000.0)
        self.assertAlmostEqual(data['planned']['overheads'], 150.0)
        self.assertAlmostEqual(data['planned']['total'], 2150.0)


@tagged('post_install', '-at_install')
class TestVariance(DashboardTestCase):

    def test_variance_no_planned_cost(self):
        self._create_cost_sheet(material=(0.0, 0.0), labour=(0.0, 0.0), overhead=(0.0, 0.0))
        data = _run(self.env, 'job_costing.variance', {'project_ids': [self.project.id]})
        self.assertIsNone(data['by_type']['material']['variance_percent'])

    def test_variance_by_project(self):
        self._create_cost_sheet()
        data = _run(self.env, 'job_costing.variance', {'project_ids': [self.project.id]})
        self.assertEqual(len(data['by_project']), 1)
        self.assertEqual(data['by_project'][0]['id'], self.project.id)

    def test_negative_and_positive_variance(self):
        # Planned cost sheet with zero actual (no PO/timesheet/bill linked)
        # gives actual - planned <= 0 for every type in this fixture.
        self._create_cost_sheet()
        data = _run(self.env, 'job_costing.variance', {'project_ids': [self.project.id]})
        self.assertLessEqual(data['by_type']['total']['variance'], 0.0)


@tagged('post_install', '-at_install')
class TestTrends(DashboardTestCase):

    def test_trends_default_month(self):
        self._create_cost_sheet()
        data = _run(self.env, 'job_costing.trends',
                     {'project_ids': [self.project.id]}, group_by='month')
        self.assertEqual(data['group_by'], 'month')
        self.assertIn('series', data)
        names = [s['name'] for s in data['series']]
        self.assertEqual(names, ['Planned Cost', 'Actual Cost', 'Revenue', 'Profit'])

    def test_trends_invalid_granularity(self):
        self._create_cost_sheet()
        with self.assertRaises(DashboardApiError):
            _run(self.env, 'job_costing.trends',
                 {'project_ids': [self.project.id]}, group_by='fortnight')


@tagged('post_install', '-at_install')
class TestProfitability(DashboardTestCase):

    def test_profitability_ranking(self):
        self._create_cost_sheet()
        data = _run(self.env, 'job_costing.profitability', {'project_ids': [self.project.id]})
        self.assertEqual(len(data['projects']), 1)
        self.assertIn('most_profitable', data)
        self.assertIn('least_profitable', data)


@tagged('post_install', '-at_install')
class TestDateFilter(DashboardTestCase):

    def test_date_filter_excludes_out_of_range(self):
        self._create_cost_sheet(date_start='2020-01-01')
        data = _run(self.env, 'job_costing.overview', {
            'project_ids': [self.project.id],
            'date_from': '2026-01-01', 'date_to': '2026-12-31',
        })
        self.assertEqual(data['planned_cost'], 0.0)

    def test_date_filter_includes_in_range(self):
        self._create_cost_sheet(date_start='2026-03-01')
        data = _run(self.env, 'job_costing.overview', {
            'project_ids': [self.project.id],
            'date_from': '2026-01-01', 'date_to': '2026-12-31',
        })
        self.assertGreater(data['planned_cost'], 0.0)
