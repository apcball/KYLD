# -*- coding: utf-8 -*-
"""Labour dashboard: planned/actual labour cost, hours, cost-per-hour,
top labour cost by employee, timesheet summary."""
from .base_service import DashboardService, register, safe_percent

TOP_N = 10


@register('job_costing.labour')
class LabourService(DashboardService):

    def compute(self, **kwargs):
        env, filters = self.env, self.filters
        cost_sheet_ids = env['job.cost.sheet'].search(
            filters.cost_sheet_domain()).ids

        totals_row = env['job.cost.line'].read_group(
            domain=[('cost_sheet_id', 'in', cost_sheet_ids), ('cost_type', '=', 'labour')],
            fields=['total_cost:sum', 'actual_cost:sum'],
            groupby=[],
            lazy=False,
        )
        row = totals_row[0] if totals_row else {}
        planned = row.get('total_cost', 0.0) or 0.0
        actual = row.get('actual_cost', 0.0) or 0.0

        timesheet_domain = [('project_id.company_id', 'in', filters.company_ids)]
        if filters.project_ids:
            timesheet_domain.append(('project_id', 'in', filters.project_ids))
        if filters.date_from:
            timesheet_domain.append(('date', '>=', filters.date_from))
        if filters.date_to:
            timesheet_domain.append(('date', '<=', filters.date_to))

        hours_row = env['account.analytic.line'].read_group(
            domain=timesheet_domain,
            fields=['unit_amount:sum'],
            groupby=[],
            lazy=False,
        )
        planned_hours = 0.0  # not tracked as a distinct field on job.cost.line for labour
        actual_hours = (hours_row[0].get('unit_amount', 0.0) or 0.0) if hours_row else 0.0
        cost_per_hour = (actual / actual_hours) if actual_hours else None

        summary = {
            'planned_cost': planned,
            'actual_cost': actual,
            'variance': actual - planned,
            'variance_percent': safe_percent(actual - planned, planned),
            'planned_hours': planned_hours,
            'actual_hours': actual_hours,
            'cost_per_hour': cost_per_hour,
        }

        by_employee = env['account.analytic.line'].read_group(
            domain=timesheet_domain,
            fields=['amount:sum', 'unit_amount:sum'],
            groupby=['employee_id'],
            lazy=False,
        )
        top_labour = sorted(
            (r for r in by_employee if r.get('employee_id')),
            key=lambda r: abs(r.get('amount', 0.0) or 0.0), reverse=True,
        )[:TOP_N]
        top_labour_out = [{
            'id': r['employee_id'][0],
            'name': r['employee_id'][1],
            'cost': abs(r.get('amount', 0.0) or 0.0),
            'hours': r.get('unit_amount', 0.0) or 0.0,
        } for r in top_labour]

        timesheet_summary = [{
            'id': r['employee_id'][0],
            'name': r['employee_id'][1],
            'hours': r.get('unit_amount', 0.0) or 0.0,
        } for r in by_employee if r.get('employee_id')]

        data = {
            'summary': summary,
            'top_labour': top_labour_out,
            'timesheet_summary': timesheet_summary,
        }
        return data
