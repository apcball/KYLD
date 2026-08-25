# -*- coding: utf-8 -*-
"""Overview, cost-breakdown, variance and trend endpoints. All figures are
produced with read_group (never an ORM query in a loop) and are converted
to a single base currency bucket-by-bucket via CurrencyResolver."""
from collections import defaultdict

from .base_service import (
    DashboardService, ProjectStatusEvaluator, is_project_completed,
    register, safe_percent,
)
from .response import DashboardApiError, ErrorCode
from .drilldown import drilldown

COST_SHEET_SUM_FIELDS = [
    'total_material_cost', 'total_labour_cost', 'total_overhead_cost', 'total_cost',
    'actual_material_cost', 'actual_labour_cost', 'actual_overhead_cost', 'actual_total_cost',
    'material_variance', 'labour_variance', 'overhead_variance', 'total_variance',
]

TREND_GRANULARITIES = {'day', 'week', 'month', 'quarter', 'year'}


def _grouped_cost_sheet_totals(env, filters, extra_groupby=None):
    """One read_group over job.cost.sheet, always grouped by currency_id
    (and company_id, needed for correct rate conversion) plus any extra
    groupby fields the caller needs (e.g. project_id)."""
    groupby = ['currency_id', 'company_id'] + (extra_groupby or [])
    return env['job.cost.sheet'].read_group(
        domain=filters.cost_sheet_domain(),
        fields=[f + ':sum' for f in COST_SHEET_SUM_FIELDS],
        groupby=groupby,
        lazy=False,
    )


def _company_map(env, filters):
    return {c.id: c for c in env['res.company'].browse(filters.company_ids)}


@register('job_costing.overview')
class JobCostingOverviewService(DashboardService):

    def compute(self, **kwargs):
        env, filters = self.env, self.filters
        companies = _company_map(env, filters)

        groups = _grouped_cost_sheet_totals(env, filters)
        totals = defaultdict(float)
        for group in groups:
            company = companies.get(group['company_id'][0]) if group.get('company_id') else env.company
            currency_id = group['currency_id'][0] if group.get('currency_id') else False
            for f in COST_SHEET_SUM_FIELDS:
                converted = self.currency.convert_grouped_amount(
                    group.get(f, 0.0) or 0.0, currency_id, company)
                totals[f] += converted

        project_domain = filters.project_domain()
        Project = env['project.project']
        projects = Project.search(project_domain)
        evaluator = ProjectStatusEvaluator(env)

        contract_amount = 0.0
        for project in projects:
            if project.contract_amount:
                contract_amount += self.currency.convert_grouped_amount(
                    project.contract_amount, project.currency_id.id, project.company_id)

        active_count = 0
        completed_count = 0
        for project in projects:
            progress = safe_percent(project.total_actual_cost, project.total_planned_cost) or 0.0
            status = evaluator.evaluate(is_project_completed(project), progress)
            if status == 'completed':
                completed_count += 1
            else:
                active_count += 1

        actual_total = totals['actual_total_cost']
        planned_total = totals['total_cost']
        planned_profit = contract_amount - planned_total
        actual_profit = contract_amount - actual_total
        profit_margin = safe_percent(actual_profit, contract_amount)
        cost_variance = actual_total - planned_total
        cost_variance_percent = safe_percent(cost_variance, planned_total)

        data = {
            'total_projects': len(projects),
            'active_projects': active_count,
            'completed_projects': completed_count,

            'contract_amount': contract_amount,

            'planned_cost': planned_total,
            'actual_cost': actual_total,

            'planned_profit': planned_profit,
            'actual_profit': actual_profit,

            'profit_margin': profit_margin,

            'cost_variance': cost_variance,
            'cost_variance_percent': cost_variance_percent,

            'material_cost': totals['actual_material_cost'],
            'labour_cost': totals['actual_labour_cost'],
            'overhead_cost': totals['actual_overhead_cost'],
        }
        return data


@register('job_costing.cost_breakdown')
class CostBreakdownService(DashboardService):

    def compute(self, **kwargs):
        env, filters = self.env, self.filters
        companies = _company_map(env, filters)
        groups = _grouped_cost_sheet_totals(env, filters)

        totals = defaultdict(float)
        for group in groups:
            company = companies.get(group['company_id'][0]) if group.get('company_id') else env.company
            currency_id = group['currency_id'][0] if group.get('currency_id') else False
            for f in COST_SHEET_SUM_FIELDS:
                totals[f] += self.currency.convert_grouped_amount(
                    group.get(f, 0.0) or 0.0, currency_id, company)

        data = {
            'planned': {
                'materials': totals['total_material_cost'],
                'labour': totals['total_labour_cost'],
                'overheads': totals['total_overhead_cost'],
                'total': totals['total_cost'],
            },
            'actual': {
                'materials': totals['actual_material_cost'],
                'labour': totals['actual_labour_cost'],
                'overheads': totals['actual_overhead_cost'],
                'total': totals['actual_total_cost'],
            },
        }
        return data


@register('job_costing.variance')
class VarianceService(DashboardService):

    def compute(self, **kwargs):
        env, filters = self.env, self.filters
        companies = _company_map(env, filters)

        overall_groups = _grouped_cost_sheet_totals(env, filters)
        overall = defaultdict(float)
        for group in overall_groups:
            company = companies.get(group['company_id'][0]) if group.get('company_id') else env.company
            currency_id = group['currency_id'][0] if group.get('currency_id') else False
            for f in COST_SHEET_SUM_FIELDS:
                overall[f] += self.currency.convert_grouped_amount(
                    group.get(f, 0.0) or 0.0, currency_id, company)

        def variance_block(planned, actual):
            variance = actual - planned
            return {
                'planned': planned,
                'actual': actual,
                'variance': variance,
                'variance_percent': safe_percent(variance, planned),
            }

        by_type = {
            'material': variance_block(overall['total_material_cost'], overall['actual_material_cost']),
            'labour': variance_block(overall['total_labour_cost'], overall['actual_labour_cost']),
            'overhead': variance_block(overall['total_overhead_cost'], overall['actual_overhead_cost']),
            'total': variance_block(overall['total_cost'], overall['actual_total_cost']),
        }

        project_groups = _grouped_cost_sheet_totals(env, filters, extra_groupby=['project_id'])
        by_project_raw = defaultdict(lambda: defaultdict(float))
        for group in project_groups:
            if not group.get('project_id'):
                continue
            project_id = group['project_id'][0]
            company = companies.get(group['company_id'][0]) if group.get('company_id') else env.company
            currency_id = group['currency_id'][0] if group.get('currency_id') else False
            for f in ('total_cost', 'actual_total_cost'):
                by_project_raw[project_id][f] += self.currency.convert_grouped_amount(
                    group.get(f, 0.0) or 0.0, currency_id, company)

        projects = env['project.project'].browse(list(by_project_raw.keys()))
        by_project = []
        for project in projects:
            row = by_project_raw[project.id]
            block = variance_block(row['total_cost'], row['actual_total_cost'])
            block.update({
                'id': project.id,
                'name': project.name,
                'drilldown': drilldown('project.project', project.id),
            })
            by_project.append(block)

        data = {
            'by_type': by_type,
            'by_project': by_project,
        }
        return data


@register('job_costing.trends')
class TrendsService(DashboardService):

    def compute(self, group_by='month', **kwargs):
        if group_by not in TREND_GRANULARITIES:
            raise DashboardApiError(
                ErrorCode.INVALID_REQUEST,
                "group_by must be one of %s" % ', '.join(sorted(TREND_GRANULARITIES)))

        env, filters = self.env, self.filters
        companies = _company_map(env, filters)

        groupby = ['date_start:%s' % group_by, 'currency_id', 'company_id']
        groups = env['job.cost.sheet'].read_group(
            domain=filters.cost_sheet_domain(),
            fields=['total_cost:sum', 'actual_total_cost:sum'],
            groupby=groupby,
            lazy=False,
        )

        buckets = defaultdict(lambda: defaultdict(float))
        period_start = {}
        for group in groups:
            period_key = group.get('date_start:%s' % group_by)
            if not period_key:
                continue
            # read_group's date groupby label ("December 2025") is not
            # lexically sortable; use the range start it ships alongside
            # the label to sort chronologically instead.
            range_from = (group.get('__range') or {}).get(
                'date_start:%s' % group_by, {}).get('from')
            if range_from:
                period_start[period_key] = range_from
            company = companies.get(group['company_id'][0]) if group.get('company_id') else env.company
            currency_id = group['currency_id'][0] if group.get('currency_id') else False
            for f in ('total_cost', 'actual_total_cost'):
                buckets[period_key][f] += self.currency.convert_grouped_amount(
                    group.get(f, 0.0) or 0.0, currency_id, company)

        ordered_periods = sorted(
            buckets.keys(), key=lambda p: period_start.get(p, p))
        contract_by_project = env['project.project'].search(filters.project_domain())
        revenue_total = sum(
            self.currency.convert_grouped_amount(
                p.contract_amount, p.currency_id.id, p.company_id)
            for p in contract_by_project if p.contract_amount
        )
        revenue_per_period = revenue_total / len(ordered_periods) if ordered_periods else 0.0

        series = [
            {'name': 'Planned Cost', 'data': [buckets[p]['total_cost'] for p in ordered_periods]},
            {'name': 'Actual Cost', 'data': [buckets[p]['actual_total_cost'] for p in ordered_periods]},
            {'name': 'Revenue', 'data': [revenue_per_period for _ in ordered_periods]},
            {'name': 'Profit', 'data': [
                revenue_per_period - buckets[p]['actual_total_cost'] for p in ordered_periods]},
        ]

        data = {
            'group_by': group_by,
            'periods': ordered_periods,
            'series': series,
        }
        return data
