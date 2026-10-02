# -*- coding: utf-8 -*-
import io
from datetime import date, timedelta

from odoo import fields, http
from odoo.exceptions import AccessError
from odoo.http import content_disposition, request

class BudgetAPI(http.Controller):

    @http.route('/budget/api/matrix', type='json', auth='user')
    def get_budget_matrix(self, plan_id):
        # We assume plan_id is the Monthly plan here as the UI will pass the monthly plan IDs.
        plan = request.env['monthly.budget.plan'].browse(plan_id)
        if not plan.exists():
            return {'error': 'Plan not found'}

        lines = request.env['monthly.budget.allocation'].search([('plan_id', '=', plan_id)])
        
        column_key = plan.date_from.strftime('%Y-%m-%d') if plan.date_from else 'empty'
        weeks = {
            column_key: {
                'key': column_key,
                'label': plan.name,
                'date_from': plan.date_from.strftime('%Y-%m-%d') if plan.date_from else '',
                'date_to': plan.date_to.strftime('%Y-%m-%d') if plan.date_to else ''
            }
        }
        sorted_weeks = [weeks[column_key]]

        rows_dict = {}
        for line in lines:
            dept_id = line.department_id.id if line.department_id else 0
            row_key = f"{dept_id}"
            
            if row_key not in rows_dict:
                dept_name = line.department_id.sudo().name if line.department_id else 'Base / General'
                rows_dict[row_key] = {
                    'key': row_key,
                    'department_id': dept_id,
                    'label': dept_name,
                    'cells': {}
                }
                
            rows_dict[row_key]['cells'][column_key] = {
                'line_id': line.id,
                'limit': line.amount,
                'forecast': line.forecast_amount,
                'used': line.amount_used,
                'reserved': line.amount_reserved,
                'available': line.amount_available_forecast
            }

        return {
            'weeks': sorted_weeks,
            'rows': list(rows_dict.values())
        }

    @http.route('/budget/api/update_cell', type='json', auth='user')
    def update_budget_cell(self, line_id, amount_limit=None, forecast_amount=None):
        if not request.env.user.has_group('biz_weekly_budget.group_budget_manager'):
            return {'error': 'Only Budget Managers can update forecasts'}
        if amount_limit is not None:
            return {
                'error': 'Budget limit is derived from the plan allocation percentage'
            }
        line = request.env['monthly.budget.allocation'].browse(line_id)
        if line.exists():
            if forecast_amount is not None:
                forecast_amount = float(forecast_amount)
                if forecast_amount < 0:
                    return {'error': 'Forecast amount cannot be negative'}
                request.env['budget.move'].search([
                    ('allocation_id', '=', line.id),
                    ('move_type', '=', 'forecast')
                ]).unlink()
                if forecast_amount > 0:
                    request.env['budget.move'].create({
                        'name': 'Manual Forecast',
                        'allocation_id': line.id,
                        'source_model': 'monthly.budget.allocation',
                        'source_id': line.id,
                        'department_id': line.department_id.id,
                        'amount': forecast_amount,
                        'move_type': 'forecast',
                        'date': line.date_to or fields.Date.today()
                    })
            return {'status': 'success'}
        return {'error': 'Line not found'}

    @http.route('/budget/api/dashboard_data', type='json', auth='user')
    def get_dashboard_data(self, selectedPlanId=None, selectedYear=None, selectedMonth=None,
                           selectedCompanyId=None, **kwargs):
        # Record rules still apply, but evaluate them against every company the
        # user belongs to (not just the ones ticked in the company switcher) so
        # the dashboard can show cross-company data; the Company filter narrows it.
        env = request.env(context=dict(
            request.env.context, allowed_company_ids=request.env.user.company_ids.ids))
        company_id = int(selectedCompanyId) if selectedCompanyId and selectedCompanyId != 'all' else False

        domain = [('plan_state', '=', 'confirmed')]
        if selectedPlanId and selectedPlanId != 'all':
            domain.append(('plan_id', '=', int(selectedPlanId)))
        if company_id:
            domain += ['|', ('company_id', '=', company_id), ('all_companies', '=', True)]

        plan_domain = [('state', '=', 'confirmed')]
        if company_id:
            plan_domain += ['|', ('company_id', '=', company_id), ('all_companies', '=', True)]
        plans = [{'id': p.id, 'name': p.name, 'year': p.year}
                 for p in env['monthly.budget.plan'].search(plan_domain, order='date_from asc')]

        BudgetAllocation = env['monthly.budget.allocation']
        lines = BudgetAllocation.search(domain, order='date_from asc')

        if selectedYear and selectedYear != 'all':
            lines = lines.filtered(lambda l: l.date_from and str(l.date_from.year) == str(selectedYear))
        if selectedMonth and selectedMonth != 'all':
            lines = lines.filtered(lambda l: l.date_from and str(l.date_from.month) == str(selectedMonth))

        # 1. SUMMARY
        summary = {
            'total_budget': sum(lines.mapped('amount')),
            'total_used': sum(lines.mapped('amount_used')),
            'total_reserved': sum(lines.mapped('amount_reserved')),
            'forecast': sum(lines.mapped('forecast_amount')),
        }
        total_budget = summary['total_budget']
        total_used = summary['total_used']
        total_reserved = summary['total_reserved']
        total_forecast = summary['forecast']

        summary['remaining'] = total_budget - total_used - total_reserved - total_forecast
        summary['utilization'] = (
            (total_used + total_reserved) / total_budget * 100) if total_budget else 0
        for key, value in (('used_pct', total_used), ('reserved_pct', total_reserved),
                           ('forecast_pct', total_forecast), ('available_pct', summary['remaining'])):
            summary[key] = (value / total_budget * 100) if total_budget else 0

        # 2. DONUT (Budget Utilization) - same "available" as the KPI card.
        # Legend shows signed values; slice size is clamped at zero.
        pie_data = {
            'labels': ['Used', 'Reserved', 'Available', 'Forecast'],
            'values': [total_used, total_reserved, summary['remaining'], total_forecast],
        }

        # 3. PER-PLAN DATA (kept for compatibility)
        months_dict = {}
        for line in lines:
            w_label = line.plan_id.name if line.plan_id else "Unknown"
            if w_label not in months_dict:
                months_dict[w_label] = {'name': w_label, 'budget': 0, 'actual': 0, 'reserved': 0,
                                        'forecast': 0, 'date_from': line.date_from}
            months_dict[w_label]['budget'] += line.amount
            months_dict[w_label]['actual'] += line.amount_used
            months_dict[w_label]['reserved'] += line.amount_reserved
            months_dict[w_label]['forecast'] += line.forecast_amount
        sorted_plans = sorted(months_dict.values(), key=lambda w: w['date_from'] or fields.Date.today())

        # 4. DEPARTMENT DATA (For Bar Chart)
        dept_dict = {}
        for line in lines:
            d_label = line.department_id.name if line.department_id else 'General'
            if d_label not in dept_dict:
                dept_dict[d_label] = {'name': d_label, 'limit': 0, 'used': 0, 'reserved': 0, 'forecast': 0}
            dept_dict[d_label]['limit'] += line.amount
            dept_dict[d_label]['used'] += line.amount_used
            dept_dict[d_label]['reserved'] += line.amount_reserved
            dept_dict[d_label]['forecast'] += line.forecast_amount

        currency = lines[:1].currency_id or env.company.currency_id

        payments_monthly = self._dashboard_payments_monthly(env, False, currency)

        return {
            'summary': summary,
            'weeks': [
                {
                    'name': w['name'],
                    'budget': w['budget'],
                    'actual': w['actual'],
                    'reserved': w['reserved'],
                    'forecast': w['forecast']
                } for w in sorted_plans
            ],
            'weekly': self._dashboard_weekly(env, lines, company_id, currency),
            'departments': list(dept_dict.values()),
            'pie_data': pie_data,
            'payments_monthly': payments_monthly['rows'],
            'payment_companies': payments_monthly['companies'],
            'plans': plans,
            'companies': [{'id': c.id, 'name': c.name} for c in env.user.company_ids],
            'updated_at': fields.Datetime.to_string(fields.Datetime.now()),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _week_start(day):
        return day - timedelta(days=day.weekday())

    def _payment_domain(self, company_id, date_from, date_to):
        domain = [
            ('payment_type', '=', 'outbound'),
            ('partner_type', '=', 'supplier'),
            ('state', 'in', ('posted', 'paid')),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]
        if company_id:
            domain.append(('company_id', '=', company_id))
        return domain

    def _convert_payment(self, payment, currency):
        if payment.currency_id == currency:
            return payment.amount
        return payment.currency_id._convert(
            payment.amount, currency, payment.company_id, payment.date or fields.Date.today())

    def _dashboard_weekly(self, env, lines, company_id, currency):
        """Mon-Sun weeks across the filtered plans' date range.

        Budget is monthly, so each week's limit is the allocation amount
        pro-rated by the days of the week falling inside its plan period.
        """
        dated = lines.filtered(lambda l: l.date_from and l.date_to)
        if not dated:
            return []
        range_from = min(dated.mapped('date_from'))
        range_to = max(dated.mapped('date_to'))
        weeks = []
        cursor = self._week_start(range_from)
        while cursor <= range_to:
            weeks.append({
                'date_from': cursor,
                'date_to': cursor + timedelta(days=6),
                'limit': 0.0, 'reserved': 0.0, 'used': 0.0, 'forecast': 0.0, 'payment': 0.0,
            })
            cursor += timedelta(days=7)
        if len(weeks) > 60:
            weeks = weeks[:60]

        for line in dated:
            plan_days = (line.date_to - line.date_from).days + 1
            for week in weeks:
                start = max(week['date_from'], line.date_from)
                end = min(week['date_to'], line.date_to)
                if start <= end:
                    week['limit'] += line.amount * ((end - start).days + 1) / plan_days

        moves = env['budget.move'].search([
            ('allocation_id', 'in', dated.ids),
            ('date', '>=', weeks[0]['date_from']),
            ('date', '<=', weeks[-1]['date_to']),
        ])
        for move in moves:
            if not move.date or move.move_type not in ('reserved', 'used', 'forecast'):
                continue
            idx = (self._week_start(move.date) - weeks[0]['date_from']).days // 7
            if 0 <= idx < len(weeks):
                weeks[idx][move.move_type] += move.amount

        payments = env['account.payment'].search(
            self._payment_domain(company_id, weeks[0]['date_from'], weeks[-1]['date_to']))
        for payment in payments:
            idx = (self._week_start(payment.date) - weeks[0]['date_from']).days // 7
            if 0 <= idx < len(weeks):
                weeks[idx]['payment'] += self._convert_payment(payment, currency)

        result = []
        for number, week in enumerate(weeks, 1):
            result.append(dict(
                week,
                label='W%d' % number,
                range='%s - %s' % (week['date_from'].strftime('%d/%m'), week['date_to'].strftime('%d/%m')),
                date_from=fields.Date.to_string(week['date_from']),
                date_to=fields.Date.to_string(week['date_to']),
            ))
        return result

    def _dashboard_payments_monthly(self, env, company_id, currency):
        """Posted outbound supplier payments for the last 12 months, per company."""
        today = fields.Date.today()
        first = today.replace(day=1)
        months = []
        for back in range(11, -1, -1):
            month = first.month - back
            year = first.year + (month - 1) // 12
            months.append((year, (month - 1) % 12 + 1))
        start = date(months[0][0], months[0][1], 1)
        buckets = {m: {'amount': 0.0, 'count': 0, 'by_company': {}} for m in months}
        companies = {}
        payments = env['account.payment'].search(
            self._payment_domain(company_id, start, today))
        for payment in payments:
            key = (payment.date.year, payment.date.month)
            if key not in buckets:
                continue
            amount = self._convert_payment(payment, currency)
            bucket = buckets[key]
            bucket['amount'] += amount
            bucket['count'] += 1
            cid = str(payment.company_id.id)
            per_company = bucket['by_company'].setdefault(cid, {'amount': 0.0, 'count': 0})
            per_company['amount'] += amount
            per_company['count'] += 1
            companies[payment.company_id.id] = payment.company_id.name
        rows = [
            {'year': y, 'month': m, 'label': date(y, m, 1).strftime('%b %Y'),
             'amount': buckets[(y, m)]['amount'], 'count': buckets[(y, m)]['count'],
             'by_company': buckets[(y, m)]['by_company']}
            for (y, m) in months
        ]
        return {
            'rows': rows,
            'companies': [{'id': cid, 'name': name} for cid, name in sorted(companies.items())],
        }

    @http.route('/budget/api/payments_export', type='http', auth='user')
    def export_payments(self, date_from=None, date_to=None, company_id=None, **kwargs):
        """Excel report of posted outbound supplier payments, grouped by company."""
        try:
            d_from = fields.Date.to_date(date_from)
            d_to = fields.Date.to_date(date_to)
        except (TypeError, ValueError):
            d_from = d_to = None
        if not d_from or not d_to or d_from > d_to:
            return request.make_response('Invalid date range', status=400)

        env = request.env(context=dict(
            request.env.context, allowed_company_ids=request.env.user.company_ids.ids))
        cid = int(company_id) if company_id and company_id != 'all' else False
        try:
            payments = env['account.payment'].search(
                self._payment_domain(cid, d_from, d_to), order='company_id, date, name')
            rows = [(
                p.company_id.name, p.name or '', p.date, p.partner_id.name or '',
                ', '.join(p.reconciled_bill_ids.mapped('name')),
                p.journal_id.name or '', p.ref or '', p.currency_id.name, p.amount,
                p.company_id.currency_id.name, self._convert_payment(p, p.company_id.currency_id),
                p.state,
            ) for p in payments]
        except AccessError:
            return request.make_response('Access denied', status=403)

        import xlsxwriter
        output = io.BytesIO()
        book = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = book.add_worksheet('Payments')
        title = book.add_format({'bold': True, 'font_size': 14})
        head = book.add_format({'bold': True, 'bg_color': '#DCE6F7', 'border': 1})
        day = book.add_format({'num_format': 'yyyy-mm-dd'})
        money = book.add_format({'num_format': '#,##0.00'})
        sub_label = book.add_format({'bold': True, 'top': 1})
        sub_money = book.add_format({'bold': True, 'top': 1, 'num_format': '#,##0.00'})

        sheet.write(0, 0, 'Actual Payment Report', title)
        sheet.write(1, 0, 'Period: %s - %s' % (d_from, d_to))
        headers = ['Company', 'Payment', 'Date', 'Vendor', 'Bill No.', 'Journal', 'Memo',
                   'Currency', 'Amount', 'Company Currency', 'Amount (Company Currency)', 'Status']
        for col, label in enumerate(headers):
            sheet.write(3, col, label, head)

        row_no = 4
        subtotal = 0.0
        grand_total = 0.0
        currencies = set()
        current = None

        def write_subtotal(row, company_name, amount, ccy, label=None):
            sheet.write(row, 0, label or 'Total ' + company_name, sub_label)
            for col in range(1, 9):
                sheet.write_blank(row, col, None, sub_label)
            sheet.write(row, 9, ccy, sub_label)
            sheet.write_number(row, 10, amount, sub_money)
            sheet.write_blank(row, 11, None, sub_label)

        last_ccy = ''
        for rec in rows:
            if current is not None and rec[0] != current:
                write_subtotal(row_no, current, subtotal, last_ccy)
                row_no += 1
                subtotal = 0.0
            current, last_ccy = rec[0], rec[9]
            for col, value in enumerate(rec):
                if col == 2:
                    sheet.write_datetime(row_no, col, value, day)
                elif col in (8, 10):
                    sheet.write_number(row_no, col, value, money)
                else:
                    sheet.write(row_no, col, value)
            subtotal += rec[10]
            grand_total += rec[10]
            currencies.add(rec[9])
            row_no += 1
        if current is not None:
            write_subtotal(row_no, current, subtotal, last_ccy)
            row_no += 1
            write_subtotal(
                row_no, '', grand_total,
                last_ccy if len(currencies) == 1 else 'Mixed',
                label='Grand Total (รวมทั้งหมด) - %d payments' % len(rows))
        sheet.set_column(0, 0, 24)
        sheet.set_column(1, 1, 18)
        sheet.set_column(2, 2, 12)
        sheet.set_column(3, 4, 28)
        sheet.set_column(5, 6, 24)
        sheet.set_column(7, 11, 16)
        sheet.freeze_panes(4, 0)
        book.close()

        filename = 'actual_payment_%s_%s.xlsx' % (d_from, d_to)
        return request.make_response(output.getvalue(), headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition(filename)),
        ])
