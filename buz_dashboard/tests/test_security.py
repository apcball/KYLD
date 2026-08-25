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
class TestDashboardAccess(DashboardTestCase):

    def test_dashboard_access_requires_valid_company(self):
        other_company = self.env['res.company'].create({'name': 'Other Co'})
        # Odoo core auto-grants the creating user access to a newly
        # created company; explicitly revoke it so this test exercises
        # the real "company the caller cannot see" path.
        self.env.user.write({'company_ids': [(3, other_company.id)]})
        with self.assertRaises(DashboardApiError):
            DashboardFilter.from_payload(
                self.env, {'company_id': other_company.id})


@tagged('post_install', '-at_install')
class TestMultiCompany(DashboardTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_b = cls.env['res.company'].create({'name': 'Company B'})
        cls.project_b = cls.env['project.project'].create({
            'name': 'Company B Project',
            'company_id': cls.company_b.id,
            'contract_amount': 500000.0,
        })

    def test_company_isolation(self):
        """The central guarantee: a user scoped to company A must never
        see company B's cost figures, even though both records exist.
        DEV is a real, non-empty shared database, so both queries are
        scoped by project_ids as well as company_id."""
        self._create_cost_sheet()  # in self.company (company A)

        env_b = self.env(context=dict(
            self.env.context, allowed_company_ids=[self.company_b.id]))
        self._create_cost_sheet_for(env_b, self.project_b, self.company_b)

        data_a = _run(self.env, 'job_costing.overview', {
            'company_id': self.company.id, 'project_ids': [self.project.id]})
        data_b = _run(env_b, 'job_costing.overview', {
            'company_id': self.company_b.id, 'project_ids': [self.project_b.id]})

        self.assertEqual(data_a['total_projects'], 1)
        self.assertEqual(data_b['total_projects'], 1)
        self.assertAlmostEqual(data_a['contract_amount'], 1000000.0)
        self.assertAlmostEqual(data_b['contract_amount'], 500000.0)

    def test_cross_company_project_id_returns_nothing(self):
        """Guessing another company's project id from within company B's
        session must not surface company A's data -- the record rule and
        the explicit company_id filter both have to hold."""
        self._create_cost_sheet()  # company A project

        env_b = self.env(context=dict(
            self.env.context, allowed_company_ids=[self.company_b.id]))
        data = _run(env_b, 'job_costing.overview', {
            'company_id': self.company_b.id, 'project_ids': [self.project.id]})
        self.assertEqual(data['total_projects'], 0)
        self.assertEqual(data['planned_cost'], 0.0)

    def _create_cost_sheet_for(self, env, project, company):
        product = env['product.product'].search(
            [('name', '=', 'Dashboard Test Material')], limit=1) or self.product
        env['job.cost.sheet'].create({
            'project_id': project.id,
            'company_id': company.id,
            'state': 'approved',
            'material_cost_ids': [(0, 0, {
                'cost_type': 'material', 'name': 'material', 'product_id': product.id,
                'planned_qty': 10.0, 'unit_cost': 20.0,
            })],
        })
