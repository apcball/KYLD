# -*- coding: utf-8 -*-
from odoo import models, api

class ReportBuzExpenseReport(models.AbstractModel):
    _name = 'report.buz_expense_report.report_expense_sheet_custom'
    _description = 'Custom Expense Report layout'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['hr.expense.sheet'].sudo().browse(docids)
        
        report_data = []
        for sheet in docs:
            # Extract distinct dates to find minimum and maximum for the subtitle
            all_dates = sheet.expense_line_ids.mapped('date')
            all_dates = [d for d in all_dates if d]
            
            date_str = ""
            if all_dates:
                min_date = min(all_dates)
                max_date = max(all_dates)
                # Format: MM/DD/YY - MM/DD/YY
                date_str = f"{min_date.strftime('%m/%d/%y')} - {max_date.strftime('%m/%d/%y')}"
            
            # Prepare lines for tabular display
            lines = []
            for line in sheet.expense_line_ids:
                lines.append({
                    'date': line.date.strftime('%-m/%-d') if line.date else '',
                    'category': line.product_id.categ_id.name if line.product_id.categ_id else '',
                    'description': line.name or '',
                    'notes': line.description or '',  # Using description field if available as notes
                    'amount': line.total_amount,
                })
            
            lines = sorted(lines, key=lambda x: x['date'])

            report_data.append({
                'doc': sheet,
                'date_str': date_str,
                'lines': lines,
                'total_amount': sum(l['amount'] for l in lines)
            })
            
        return {
            'docs': docs,
            'report_data': report_data,
        }
