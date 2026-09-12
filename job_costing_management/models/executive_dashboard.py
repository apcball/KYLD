from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class JobCostSheet(models.Model):
    _inherit = 'job.cost.sheet'

    @api.model
    def get_executive_dashboard(self, filters=None, page=0):
        """Read-only snapshot. All domains are constructed server-side, under caller ACLs."""
        if not self.env.user.has_group('job_costing_management.group_job_costing_manager'):
            raise AccessError(_('Only Job Costing Managers can access this dashboard.'))
        self.check_access_rights('read')
        filters = filters or {}
        company_id = int(filters.get('company_id') or self.env.company.id)
        if company_id not in self.env.companies.ids:
            raise AccessError(_('Company is not enabled in your current session.'))
        states = filters.get('states', ['approved'])
        if not isinstance(states, list) or not states or set(states) - {'approved', 'draft', 'done'}:
            raise ValidationError(_('Select at least one valid Cost Sheet status.'))
        domain = [('company_id', '=', company_id), ('state', 'in', states)]
        start = fields.Date.to_date(filters.get('date_from'))
        end = fields.Date.to_date(filters.get('date_to'))
        if start and end and start > end:
            raise ValidationError(_('Start date must not be after end date.'))
        if start:
            domain.append(('date_start', '>=', fields.Date.to_string(start)))
        if end:
            domain.append(('date_start', '<=', fields.Date.to_string(end)))
        # Derive project choices from accessible sheets, never sudo project data.
        project_groups = self.read_group(domain, ['project_id'], ['project_id'], lazy=False)
        projects = sorted([{'id': g['project_id'][0], 'name': g['project_id'][1]}
                           for g in project_groups if g['project_id']], key=lambda p: p['name'])
        if filters.get('project_id'):
            domain.append(('project_id', '=', int(filters['project_id'])))
        field_names = ['name', 'project_id', 'currency_id', 'company_id', 'state', 'date_start',
                       'boq_total_cost', 'actual_total_cost', 'active_total_cost']
        for kind in ('material', 'labour', 'overhead'):
            field_names += ['boq_%s_cost' % kind, 'actual_%s_cost' % kind]
        sheets = self.search_read(domain, field_names, order='id')
        company = self.env['res.company'].browse(company_id)
        buckets = {}
        attention = []
        for sheet in sheets:
            currency_id = sheet['currency_id'][0] if sheet['currency_id'] else company.currency_id.id
            if currency_id not in buckets:
                currency = self.env['res.currency'].browse(currency_id)
                buckets[currency_id] = {
                    'currency_id': currency_id, 'currency': currency.name,
                    'is_company_currency': currency_id == company.currency_id.id,
                    'over_ids': [],
                    'digits': currency.decimal_places, 'budget': 0.0, 'actual': 0.0, 'active': 0.0,
                    'comparable_actual': 0.0, 'unbudgeted_actual': 0.0,
                    'over_count': 0, 'unbudgeted_count': 0, 'fallback_count': 0,
                    'count': 0, 'projects': {}, 'trend': {}, 'items': [],
                    'categories': {k: {'budget': 0.0, 'actual': 0.0, 'active': 0.0} for k in
                                   ('material', 'labour', 'overhead')},
                    'composition': {k: 0.0 for k in ('material', 'labour', 'overhead')},
                }
            bucket = buckets[currency_id]
            budget, actual = sheet['boq_total_cost'], sheet['actual_total_cost']
            comparable = budget > 0
            ratio = actual / budget * 100 if comparable else None
            status = ('unbudgeted' if not comparable else
                      'over' if actual > budget else 'near' if ratio >= 90 else 'normal')
            row = {'id': sheet['id'], 'name': sheet['name'],
                   'project_id': sheet['project_id'][0], 'project': sheet['project_id'][1],
                   'budget': budget if comparable else None, 'actual': actual,
                   'remaining': budget - actual if comparable else None,
                   'ratio': ratio, 'status': status, 'currency': bucket['currency'],
                   'currency_id': currency_id, 'digits': bucket['digits'],
                   'date': fields.Date.to_string(sheet['date_start']) if sheet['date_start'] else False}
            if status != 'normal':
                attention.append(row)
            project_id = row['project_id']
            project = bucket['projects'].setdefault(project_id, {
                'id': project_id, 'name': row['project'], 'count': 0,
                'budget': 0.0, 'actual': 0.0, 'active': 0.0, 'comparable_actual': 0.0,
                'unbudgeted_count': 0,
            })
            for target in (bucket, project):
                target['count'] += 1
                target['actual'] += actual
                target['active'] += sheet['active_total_cost']
                target['budget'] += budget if comparable else 0
                target['comparable_actual'] += actual if comparable else 0
                target['unbudgeted_count'] += int(not comparable)
            bucket['over_count'] += int(status == 'over')
            if status == 'over':
                bucket['over_ids'].append(sheet['id'])
            bucket['fallback_count'] += int(not sheet['currency_id'])
            bucket['unbudgeted_actual'] += actual if not comparable else 0
            for kind, values in bucket['categories'].items():
                bucket['composition'][kind] += sheet['actual_%s_cost' % kind]
                values['actual'] += sheet['actual_%s_cost' % kind]
                if comparable:
                    values['budget'] += sheet['boq_%s_cost' % kind]
            if row['date']:
                month = row['date'][:7]
                trend = bucket['trend'].setdefault(month, {'budget': 0.0, 'actual': 0.0, 'active': 0.0})
                trend['budget'] += budget if comparable else 0
                trend['actual'] += actual
                trend['active'] += sheet['active_total_cost']
        # Cost lines use the same sheet selection and the caller's record rules.
        # Item actuals are linked-line costs; sheet actuals may also include
        # analytic costs without a BOQ item, so they must not be allocated by guess.
        sheet_by_id = {s['id']: s for s in sheets}
        lines = self.env['job.cost.line'].search_read(
            [('cost_sheet_id', 'in', list(sheet_by_id))],
            ['name', 'cost_sheet_id', 'cost_type', 'active_total_cost',
             'boq_total_cost', 'actual_cost'])
        for line in lines:
            sheet = sheet_by_id[line['cost_sheet_id'][0]]
            currency_id = sheet['currency_id'][0] if sheet['currency_id'] else company.currency_id.id
            bucket = buckets[currency_id]
            bucket['categories'][line['cost_type']]['active'] += line['active_total_cost']
            budget, actual = line['boq_total_cost'], line['actual_cost']
            if budget > 0 and actual != budget:
                bucket['items'].append({
                    'id': line['id'], 'name': line['name'], 'sheet_id': sheet['id'],
                    'project_id': sheet['project_id'][0], 'project': sheet['project_id'][1],
                    'budget': budget, 'actual': actual, 'variance': actual - budget,
                    'ratio': (actual - budget) / budget * 100,
                })
        for bucket in buckets.values():
            for target in [bucket, *bucket['projects'].values()]:
                target['remaining'] = target['budget'] - target['comparable_actual']
                target['ratio'] = (target['comparable_actual'] / target['budget'] * 100
                                   if target['budget'] > 0 else None)
            bucket['projects'] = sorted(bucket['projects'].values(), key=lambda p: p['name'])
            bucket['items'] = sorted(bucket['items'],
                                     key=lambda r: (-abs(r['variance']), r['id']))[:5]
            cumulative = {'budget': 0.0, 'actual': 0.0, 'active': 0.0}
            trend = []
            for month, values in sorted(bucket['trend'].items()):
                for key in cumulative:
                    cumulative[key] += values[key]
                trend.append(dict(cumulative, month=month))
            bucket['trend'] = trend
            bucket['categories'] = [dict(values, key=kind) for kind, values in bucket['categories'].items()]
        attention.sort(key=lambda r: (
            {'over': 0, 'near': 1, 'unbudgeted': 2}[r['status']],
            -(r['ratio'] or 0), r['id']))
        page_size = 20
        page = max(0, min(int(page), max(0, (len(attention) - 1) // page_size)))
        return {
            'groups': sorted(buckets.values(), key=lambda b: b['currency']),
            'projects': projects,
            'companies': [{'id': c.id, 'name': c.name} for c in self.env.companies],
            'company_id': company_id, 'domain': domain,
            'attention': attention[page * page_size:(page + 1) * page_size],
            'attention_count': len(attention), 'page': page, 'page_size': page_size,
            'updated_at': fields.Datetime.to_string(fields.Datetime.now()),
        }
