# -*- coding: utf-8 -*-
"""Overhead dashboard.

NOTE (documented limitation, see README): job_costing_management's
_compute_actual_qty hard-codes actual_qty = 0 for cost_type == 'overhead',
so actual_overhead_cost is structurally ~0 on every cost sheet. This
service reports whatever the upstream module computes; it does not
fabricate an actual figure that the source data does not have.
"""
from .base_service import DashboardService, register, safe_percent


@register('job_costing.overheads')
class OverheadService(DashboardService):

    def compute(self, **kwargs):
        env, filters = self.env, self.filters
        cost_sheet_ids = env['job.cost.sheet'].search(
            filters.cost_sheet_domain()).ids

        totals_row = env['job.cost.line'].read_group(
            domain=[('cost_sheet_id', 'in', cost_sheet_ids), ('cost_type', '=', 'overhead')],
            fields=['total_cost:sum', 'actual_cost:sum'],
            groupby=[],
            lazy=False,
        )
        row = totals_row[0] if totals_row else {}
        planned = row.get('total_cost', 0.0) or 0.0
        actual = row.get('actual_cost', 0.0) or 0.0

        by_product = env['job.cost.line'].read_group(
            domain=[('cost_sheet_id', 'in', cost_sheet_ids), ('cost_type', '=', 'overhead')],
            fields=['total_cost:sum', 'actual_cost:sum'],
            groupby=['product_id'],
            lazy=False,
        )
        by_category = [{
            'id': r['product_id'][0],
            'name': r['product_id'][1],
            'planned_cost': r.get('total_cost', 0.0) or 0.0,
            'actual_cost': r.get('actual_cost', 0.0) or 0.0,
        } for r in by_product if r.get('product_id')]

        by_project_rows = env['job.cost.line'].read_group(
            domain=[('cost_sheet_id', 'in', cost_sheet_ids), ('cost_type', '=', 'overhead')],
            fields=['total_cost:sum', 'actual_cost:sum'],
            groupby=['cost_sheet_id'],
            lazy=False,
        )
        sheets = env['job.cost.sheet'].browse(
            [r['cost_sheet_id'][0] for r in by_project_rows if r.get('cost_sheet_id')])
        sheet_project_map = {s.id: s.project_id for s in sheets}
        by_project = {}
        for r in by_project_rows:
            if not r.get('cost_sheet_id'):
                continue
            project = sheet_project_map.get(r['cost_sheet_id'][0])
            if not project:
                continue
            entry = by_project.setdefault(project.id, {
                'id': project.id, 'name': project.name,
                'planned_cost': 0.0, 'actual_cost': 0.0,
            })
            entry['planned_cost'] += r.get('total_cost', 0.0) or 0.0
            entry['actual_cost'] += r.get('actual_cost', 0.0) or 0.0

        trend_rows = env['job.cost.sheet'].read_group(
            domain=filters.cost_sheet_domain(),
            fields=['total_overhead_cost:sum', 'actual_overhead_cost:sum'],
            groupby=['date_start:month'],
            lazy=False,
        )
        trend = [{
            'period': r.get('date_start:month'),
            'planned_cost': r.get('total_overhead_cost', 0.0) or 0.0,
            'actual_cost': r.get('actual_overhead_cost', 0.0) or 0.0,
        } for r in trend_rows if r.get('date_start:month')]

        data = {
            'summary': {
                'planned_cost': planned,
                'actual_cost': actual,
                'variance': actual - planned,
                'variance_percent': safe_percent(actual - planned, planned),
            },
            'by_category': by_category,
            'by_project': list(by_project.values()),
            'trend': trend,
        }
        return data
