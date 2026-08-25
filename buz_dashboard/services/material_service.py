# -*- coding: utf-8 -*-
"""Material dashboard: planned/actual material cost, variance, consumption,
procurement, requisition shortage, top materials by cost and variance."""
from collections import defaultdict

from .base_service import DashboardService, register, safe_percent

TOP_N = 10


@register('job_costing.materials')
class MaterialService(DashboardService):

    def compute(self, **kwargs):
        env, filters = self.env, self.filters
        cost_sheet_ids = env['job.cost.sheet'].search(
            filters.cost_sheet_domain()).ids

        line_totals = env['job.cost.line'].read_group(
            domain=[('cost_sheet_id', 'in', cost_sheet_ids), ('cost_type', '=', 'material')],
            fields=['total_cost:sum', 'actual_cost:sum'],
            groupby=[],
            lazy=False,
        )
        summary_row = line_totals[0] if line_totals else {}
        planned = summary_row.get('total_cost', 0.0) or 0.0
        actual = summary_row.get('actual_cost', 0.0) or 0.0
        summary = {
            'planned_cost': planned,
            'actual_cost': actual,
            'variance': actual - planned,
            'variance_percent': safe_percent(actual - planned, planned),
        }

        by_product = env['job.cost.line'].read_group(
            domain=[('cost_sheet_id', 'in', cost_sheet_ids), ('cost_type', '=', 'material')],
            fields=['total_cost:sum', 'actual_cost:sum'],
            groupby=['product_id'],
            lazy=False,
        )
        top_materials = sorted(
            (row for row in by_product if row.get('product_id')),
            key=lambda r: r.get('actual_cost', 0.0) or 0.0, reverse=True,
        )[:TOP_N]
        top_materials_out = [{
            'id': row['product_id'][0],
            'name': row['product_id'][1],
            'planned_cost': row.get('total_cost', 0.0) or 0.0,
            'actual_cost': row.get('actual_cost', 0.0) or 0.0,
        } for row in top_materials]

        variance_rows = sorted(
            (row for row in by_product if row.get('product_id')),
            key=lambda r: abs((r.get('actual_cost', 0.0) or 0.0) - (r.get('total_cost', 0.0) or 0.0)),
            reverse=True,
        )[:TOP_N]
        top_variance_out = [{
            'id': row['product_id'][0],
            'name': row['product_id'][1],
            'planned_cost': row.get('total_cost', 0.0) or 0.0,
            'actual_cost': row.get('actual_cost', 0.0) or 0.0,
            'variance': (row.get('actual_cost', 0.0) or 0.0) - (row.get('total_cost', 0.0) or 0.0),
        } for row in variance_rows]

        mr_line_domain = [('requisition_id.project_id', 'in', filters.project_ids)] \
            if filters.project_ids else []
        mr_line_domain += [('requisition_id.company_id', 'in', filters.company_ids)]
        # received_qty is a non-stored compute on material.requisition.line
        # (derived from linked PO lines), so it cannot be summed via SQL in
        # read_group; quantity is grouped by product_id and received_qty is
        # aggregated in Python from a single batch read (no query in a loop).
        mr_lines = env['material.requisition.line'].search(mr_line_domain)
        mr_line_data = mr_lines.read(['product_id', 'quantity', 'received_qty'])
        by_product = defaultdict(lambda: {'requested_qty': 0.0, 'received_qty': 0.0})
        product_names = {}
        for line in mr_line_data:
            if not line.get('product_id'):
                continue
            product_id, product_name = line['product_id']
            product_names[product_id] = product_name
            by_product[product_id]['requested_qty'] += line.get('quantity', 0.0) or 0.0
            by_product[product_id]['received_qty'] += line.get('received_qty', 0.0) or 0.0

        consumption = []
        shortage = []
        for product_id, totals in by_product.items():
            entry = {
                'id': product_id,
                'name': product_names[product_id],
                'requested_qty': totals['requested_qty'],
                'received_qty': totals['received_qty'],
            }
            consumption.append(entry)
            remaining = totals['requested_qty'] - totals['received_qty']
            if remaining > 0:
                shortage.append({**entry, 'shortage_qty': remaining})

        po_line_domain = [('job_cost_line_id.cost_sheet_id', 'in', cost_sheet_ids)]
        procurement_rows = env['purchase.order.line'].read_group(
            domain=po_line_domain,
            fields=['price_subtotal:sum', 'qty_received:sum'],
            groupby=['product_id'],
            lazy=False,
        )
        procurement = [{
            'id': row['product_id'][0],
            'name': row['product_id'][1],
            'amount': row.get('price_subtotal', 0.0) or 0.0,
            'qty_received': row.get('qty_received', 0.0) or 0.0,
        } for row in procurement_rows if row.get('product_id')]

        data = {
            'summary': summary,
            'top_materials': top_materials_out,
            'variance': top_variance_out,
            'consumption': consumption,
            'shortage': shortage,
            'procurement': procurement,
        }
        return data
