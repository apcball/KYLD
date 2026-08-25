# -*- coding: utf-8 -*-
"""Project list and project-detail endpoints."""
from collections import defaultdict

from .base_service import (
    DashboardService, ProjectStatusEvaluator, is_project_completed,
    register, safe_percent,
)
from .response import DashboardApiError, ErrorCode
from .drilldown import drilldown, odoo_action

COST_SHEET_FIELDS = ['total_cost:sum', 'actual_total_cost:sum']


def _project_cost_totals(env, filters, currency_resolver):
    """One read_group of job.cost.sheet grouped by project/currency/company,
    converted into a {project_id: {'planned':..,'actual':..}} map."""
    groups = env['job.cost.sheet'].read_group(
        domain=filters.cost_sheet_domain(),
        fields=COST_SHEET_FIELDS,
        groupby=['project_id', 'currency_id', 'company_id'],
        lazy=False,
    )
    companies = {c.id: c for c in env['res.company'].browse(filters.company_ids)}
    totals = defaultdict(lambda: defaultdict(float))
    for group in groups:
        if not group.get('project_id'):
            continue
        project_id = group['project_id'][0]
        company = companies.get(group['company_id'][0]) if group.get('company_id') else env.company
        currency_id = group['currency_id'][0] if group.get('currency_id') else False
        totals[project_id]['planned'] += currency_resolver.convert_grouped_amount(
            group.get('total_cost', 0.0) or 0.0, currency_id, company)
        totals[project_id]['actual'] += currency_resolver.convert_grouped_amount(
            group.get('actual_total_cost', 0.0) or 0.0, currency_id, company)
    return totals


@register('job_costing.projects')
class ProjectListService(DashboardService):

    def compute(self, **kwargs):
        env, filters = self.env, self.filters
        evaluator = ProjectStatusEvaluator(env)
        cost_totals = _project_cost_totals(env, filters, self.currency)

        Project = env['project.project']
        projects = Project.search(filters.project_domain())
        # sort/paginate in memory over the already-filtered, already-small
        # project recordset -- no per-project query inside this loop.
        projects = projects.sorted(key=lambda p: p.name or '')
        total_count = len(projects)
        page = projects[filters.offset:filters.offset + filters.limit]

        rows = []
        for project in page:
            costs = cost_totals.get(project.id, {'planned': 0.0, 'actual': 0.0})
            planned_cost = costs['planned']
            actual_cost = costs['actual']
            contract_amount = self.currency.convert_grouped_amount(
                project.contract_amount, project.currency_id.id, project.company_id
            ) if project.contract_amount else 0.0
            planned_profit = contract_amount - planned_cost
            actual_profit = contract_amount - actual_cost
            cost_progress = safe_percent(actual_cost, planned_cost) or 0.0
            profit_margin = safe_percent(actual_profit, contract_amount)
            variance = actual_cost - planned_cost
            status = evaluator.evaluate(is_project_completed(project), cost_progress)

            rows.append({
                'id': project.id,
                'name': project.name,
                'manager': {
                    'id': project.project_manager_id.id,
                    'name': project.project_manager_id.name,
                } if project.project_manager_id else None,
                'contract_amount': contract_amount,
                'planned_cost': planned_cost,
                'actual_cost': actual_cost,
                'planned_profit': planned_profit,
                'actual_profit': actual_profit,
                'cost_progress': cost_progress,
                'profit_margin': profit_margin,
                'variance': variance,
                'status': status,
                'drilldown': drilldown('project.project', project.id),
                'odoo_action': odoo_action('project.project', project.id),
            })

        return {
            'items': rows,
            'total_count': total_count,
            'limit': filters.limit,
            'offset': filters.offset,
        }


@register('job_costing.project_detail')
class ProjectDetailService(DashboardService):

    def compute(self, project_id=None, **kwargs):
        env = self.env
        if not project_id:
            raise DashboardApiError(ErrorCode.INVALID_REQUEST, "project_id is required")

        # Record rules already scope this browse; a hidden or non-existent
        # project both resolve to an empty recordset, so there is no
        # existence oracle for records outside the user's access.
        project = env['project.project'].browse(int(project_id))
        if not project.exists():
            raise DashboardApiError(ErrorCode.PROJECT_NOT_FOUND, "Project not found")

        cost_sheets = project.job_cost_sheet_ids
        cost_line_groups = env['job.cost.line'].read_group(
            domain=[('cost_sheet_id', 'in', cost_sheets.ids)],
            fields=['total_cost:sum', 'actual_cost:sum'],
            groupby=['cost_type'],
            lazy=False,
        )
        by_type = {g['cost_type']: {
            'planned': g.get('total_cost', 0.0) or 0.0,
            'actual': g.get('actual_cost', 0.0) or 0.0,
        } for g in cost_line_groups}

        material_requisitions = env['material.requisition'].search(
            [('project_id', '=', project.id)])
        purchase_orders = env['purchase.order'].search(
            [('project_id', '=', project.id)])
        vendor_bills = env['account.move'].search(
            [('project_id', '=', project.id), ('move_type', '=', 'in_invoice')])
        timesheets = env['account.analytic.line'].search(
            [('project_id', '=', project.id)])

        planned_cost = project.total_planned_cost
        actual_cost = project.total_actual_cost
        contract_amount = self.currency.convert_grouped_amount(
            project.contract_amount, project.currency_id.id, project.company_id
        ) if project.contract_amount else 0.0
        cost_progress = safe_percent(actual_cost, planned_cost) or 0.0
        profit = contract_amount - actual_cost
        profit_margin = safe_percent(profit, contract_amount)

        data = {
            'project': {
                'id': project.id,
                'name': project.name,
                'client': project.client_id.name if project.client_id else None,
                'manager': project.project_manager_id.name if project.project_manager_id else None,
                'job_type': project.job_type_id.name if project.job_type_id else None,
                'drilldown': drilldown('project.project', project.id),
            },
            'contract': {
                'contract_amount': contract_amount,
                'contract_date': str(project.contract_date) if project.contract_date else None,
            },
            'summary': {
                'planned_cost': planned_cost,
                'actual_cost': actual_cost,
                'cost_variance': project.cost_variance,
                'budget_utilization': project.budget_utilization,
                'cost_progress': cost_progress,
            },
            'materials': by_type.get('material', {'planned': 0.0, 'actual': 0.0}),
            'labour': by_type.get('labour', {'planned': 0.0, 'actual': 0.0}),
            'overheads': by_type.get('overhead', {'planned': 0.0, 'actual': 0.0}),
            'procurement': {
                'requisition_count': len(material_requisitions),
                'purchase_order_count': len(purchase_orders),
            },
            'inventory': {
                'picking_count': len(purchase_orders.mapped('picking_ids')),
            },
            'profitability': {
                'contract_amount': contract_amount,
                'actual_cost': actual_cost,
                'gross_profit': profit,
                'profit_margin': profit_margin,
            },
            'variance': {
                'cost_variance': project.cost_variance,
                'cost_variance_percent': safe_percent(project.cost_variance, planned_cost),
            },
            'progress': {
                'cost_progress': cost_progress,
                'vendor_bill_count': len(vendor_bills),
                'timesheet_count': len(timesheets),
            },
        }
        return data
