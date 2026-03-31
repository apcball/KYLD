# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class BudgetAPI(http.Controller):

    @http.route('/budget/api/matrix', type='json', auth='user')
    def get_budget_matrix(self, plan_id):
        plan = request.env['weekly.budget.plan'].browse(plan_id)
        if not plan.exists():
            return {'error': 'Plan not found'}

        lines = request.env['weekly.budget.line'].search([('plan_id', '=', plan_id)], order='date_from asc')
        
        # build weeks (columns)
        # assuming action_generate_weeks was called or we dynamically compute from lines
        weeks = {}
        for line in lines:
            weeks[line.date_from.strftime('%Y-%m-%d')] = {
                'label': line.name,
                'date_from': line.date_from.strftime('%Y-%m-%d'),
                'date_to': line.date_to.strftime('%Y-%m-%d')
            }
        
        # sort columns
        sorted_weeks = sorted(weeks.values(), key=lambda w: w['date_from'])

        # build rows
        rows_dict = {}
        for line in lines:
            dept_id = line.department_id.id if line.department_id else 0
            acc_id = line.analytic_account_id.id if line.analytic_account_id else 0
            row_key = f"{dept_id}_{acc_id}"
            
            if row_key not in rows_dict:
                dept_name = line.department_id.name if line.department_id else 'Company'
                acc_name = line.analytic_account_id.name if line.analytic_account_id else 'General'
                rows_dict[row_key] = {
                    'key': row_key,
                    'department_id': dept_id,
                    'analytic_account_id': acc_id,
                    'label': f"{dept_name} / {acc_name}",
                    'cells': {}
                }
                
            rows_dict[row_key]['cells'][line.date_from.strftime('%Y-%m-%d')] = {
                'line_id': line.id,
                'limit': line.amount_limit,
                'used': line.amount_used,
                'reserved': line.amount_reserved,
                'available': line.amount_available
            }

        return {
            'weeks': sorted_weeks,
            'rows': list(rows_dict.values())
        }

    @http.route('/budget/api/update_cell', type='json', auth='user')
    def update_budget_cell(self, line_id, amount_limit):
        line = request.env['weekly.budget.line'].browse(line_id)
        if line.exists():
            line.write({'amount_limit': float(amount_limit)})
            return {'status': 'success'}
        return {'error': 'Line not found'}

    @http.route('/budget/api/dashboard_data', type='json', auth='user')
    def get_dashboard_data(self, selectedPlanId=None, selectedYear=None, selectedMonth=None, **kwargs):
        domain = [('plan_state', '=', 'confirmed')]
        
        if selectedPlanId and selectedPlanId != 'all':
            domain.append(('plan_id', '=', int(selectedPlanId)))
            
        lines = request.env['weekly.budget.line'].search(domain, order='date_from asc')
        
        if selectedYear and selectedYear != 'all':
            lines = lines.filtered(lambda l: str(l.date_from.year) == str(selectedYear))
        if selectedMonth and selectedMonth != 'all':
            lines = lines.filtered(lambda l: str(l.date_from.month) == str(selectedMonth))
                
        summary = {
            'total_budget': sum(lines.mapped('amount_limit')),
            'total_used': sum(lines.mapped('amount_used')),
            'total_reserved': sum(lines.mapped('amount_reserved')),
        }
        total_spent = summary['total_used'] + summary['total_reserved']
        summary['total_actual'] = summary['total_used']
        summary['remaining'] = summary['total_budget'] - total_spent
        summary['utilization'] = (total_spent / summary['total_budget'] * 100) if summary['total_budget'] else 0

        weeks_data = {}
        for line in lines:
            w_label = line.name
            if w_label not in weeks_data:
                weeks_data[w_label] = {'name': w_label, 'budget': 0, 'actual': 0, 'reserved': 0}
            weeks_data[w_label]['budget'] += line.amount_limit
            weeks_data[w_label]['actual'] += line.amount_used
            weeks_data[w_label]['reserved'] += line.amount_reserved

        dept_data = {}
        for line in lines:
            d_label = line.department_id.name if line.department_id else 'General'
            if d_label not in dept_data:
                dept_data[d_label] = 0
            dept_data[d_label] += line.amount_used + line.amount_reserved

        return {
            'summary': summary,
            'weeks': list(weeks_data.values()),
            'pie_data': {
                'labels': list(dept_data.keys()),
                'values': list(dept_data.values())
            }
        }
