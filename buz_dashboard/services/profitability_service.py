# -*- coding: utf-8 -*-
"""Profitability dashboard: contract - actual cost = gross profit, margin %,
and project rankings (most/least profitable, highest variance, highest
revenue)."""
from .base_service import DashboardService, register, safe_percent
from .drilldown import drilldown

TOP_N = 10


@register('job_costing.profitability')
class ProfitabilityService(DashboardService):

    def compute(self, **kwargs):
        env, filters = self.env, self.filters

        cost_groups = env['job.cost.sheet'].read_group(
            domain=filters.cost_sheet_domain(),
            fields=['actual_total_cost:sum'],
            groupby=['project_id'],
            lazy=False,
        )
        actual_by_project = {
            g['project_id'][0]: g.get('actual_total_cost', 0.0) or 0.0
            for g in cost_groups if g.get('project_id')
        }

        projects = env['project.project'].search(filters.project_domain())
        rows = []
        for project in projects:
            actual_cost = actual_by_project.get(project.id, 0.0)
            contract_amount = self.currency.convert_grouped_amount(
                project.contract_amount, project.currency_id.id, project.company_id
            ) if project.contract_amount else 0.0
            gross_profit = contract_amount - actual_cost
            margin = safe_percent(gross_profit, contract_amount)
            variance = actual_cost - project.total_planned_cost
            rows.append({
                'id': project.id,
                'name': project.name,
                'contract_amount': contract_amount,
                'actual_cost': actual_cost,
                'gross_profit': gross_profit,
                'profit_margin': margin,
                'cost_variance': variance,
                'drilldown': drilldown('project.project', project.id),
            })

        def top(rows_, key, reverse=True):
            ranked = sorted(
                (r for r in rows_ if r[key] is not None), key=lambda r: r[key], reverse=reverse)
            return ranked[:TOP_N]

        data = {
            'projects': rows,
            'most_profitable': top(rows, 'gross_profit', reverse=True),
            'least_profitable': top(rows, 'gross_profit', reverse=False),
            'highest_cost_variance': top(rows, 'cost_variance', reverse=True),
            'highest_revenue': top(rows, 'contract_amount', reverse=True),
        }
        return data
