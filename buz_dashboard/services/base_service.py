# -*- coding: utf-8 -*-
from .cache import get_cache_backend, get_cache_ttl, cache_key
from .currency import CurrencyResolver
from .response import kpi as make_kpi

SERVICE_REGISTRY = {}


def register(code):
    """Class decorator registering a DashboardService under `code`, e.g.
    'job_costing.overview'. Adding a new business domain later (sales,
    purchase, stock, accounting) means adding a new file with new
    @register(...) classes; the controller layer never changes."""

    def _decorator(service_cls):
        service_cls.code = code
        SERVICE_REGISTRY[code] = service_cls
        return service_cls

    return _decorator


class DashboardService:
    """Base class for all dashboard endpoint services.

    Subclasses implement `compute()` and are looked up from
    SERVICE_REGISTRY by `run()`, which wraps the computation with cache
    lookup/store. Cache keys are uid- and company-scoped (see cache.py) so
    the cache can never leak data across a security boundary.
    """

    code = None

    def __init__(self, env, filters):
        self.env = env
        self.filters = filters
        self.currency = CurrencyResolver(env, filters)

    @property
    def cache_ttl(self):
        return get_cache_ttl(self.env)

    def run(self, **kwargs):
        backend = get_cache_backend(self.env)
        key = cache_key(self.code, self.env, self.filters)
        cached = backend.get(key)
        if cached is not None:
            return cached
        result = self.compute(**kwargs)
        backend.set(key, result, ttl=self.cache_ttl)
        return result

    def compute(self, **kwargs):
        raise NotImplementedError

    def kpi(self, value, formatted_value=None, trend=None):
        return make_kpi(
            value,
            currency=self.currency.base_currency.name,
            formatted_value=formatted_value,
            trend=trend,
        )


class ProjectStatusEvaluator:
    """Single implementation of the on_track/warning/critical/completed
    threshold logic (§8): thresholds are configurable, never hard-coded."""

    def __init__(self, env):
        params = env['ir.config_parameter'].sudo()
        self.warning_threshold = float(
            params.get_param('buz_dashboard.threshold_warning', 90.0))
        self.critical_threshold = float(
            params.get_param('buz_dashboard.threshold_critical', 100.0))

    def evaluate(self, is_completed, cost_progress):
        if is_completed:
            return 'completed'
        if cost_progress >= self.critical_threshold:
            return 'critical'
        if cost_progress >= self.warning_threshold:
            return 'warning'
        return 'on_track'


def is_project_completed(project):
    """Feature-detects the core project.project status field, since it
    could not be verified against this deployment's Odoo build offline.
    Falls back to a fact confirmed to exist: all job cost sheets done."""
    if 'last_update_status' in project._fields:
        return project.last_update_status == 'done'
    if project.job_cost_sheet_ids:
        return all(sheet.state == 'done' for sheet in project.job_cost_sheet_ids)
    return False


def safe_percent(numerator, denominator):
    """Guards every variance-percent computation against division by
    zero; returns None (not a fake 0.0) when there is no baseline."""
    if not denominator:
        return None
    return (numerator / denominator) * 100.0
