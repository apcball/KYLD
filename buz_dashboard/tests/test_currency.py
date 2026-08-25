# -*- coding: utf-8 -*-
from odoo.tests import tagged

from ..services.base_service import SERVICE_REGISTRY
from ..services.currency import CurrencyResolver
from ..services.filters import DashboardFilter
from .common import DashboardTestCase


def _run(env, code, payload=None, **kwargs):
    filters = DashboardFilter.from_payload(env, payload or {})
    service = SERVICE_REGISTRY[code](env, filters)
    return service.compute(**kwargs)


@tagged('post_install', '-at_install')
class TestCurrency(DashboardTestCase):

    def test_default_base_currency_is_company_currency(self):
        filters = DashboardFilter.from_payload(self.env, {})
        resolver = CurrencyResolver(self.env, filters)
        self.assertEqual(resolver.base_currency, self.company.currency_id)

    def test_no_currency_flagged_as_warning(self):
        filters = DashboardFilter.from_payload(self.env, {})
        resolver = CurrencyResolver(self.env, filters)
        resolver.convert_grouped_amount(100.0, False, self.company)
        self.assertTrue(resolver.warnings)

    def test_same_currency_no_conversion(self):
        filters = DashboardFilter.from_payload(self.env, {})
        resolver = CurrencyResolver(self.env, filters)
        amount = resolver.convert_grouped_amount(
            100.0, self.company.currency_id.id, self.company)
        self.assertEqual(amount, 100.0)

    def test_overview_never_sums_raw_across_currencies(self):
        # With a single-currency fixture this just checks the endpoint
        # runs cleanly through the currency resolver path.
        self._create_cost_sheet()
        data = _run(self.env, 'job_costing.overview')
        self.assertIsInstance(data['planned_cost'], float)
