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
                # Format: DD/MM/YYYY - DD/MM/YYYY
                date_str = f"{min_date.strftime('%d/%m/%Y')} - {max_date.strftime('%d/%m/%Y')}"
            
            # Prepare lines for tabular display
            lines = []
            for line in sheet.expense_line_ids:
                lines.append({
                    'date': line.date.strftime('%d/%m/%Y') if line.date else '',
                    'category': line.product_id.categ_id.name if line.product_id.categ_id else '',
                    'description': line.name or '',
                    'notes': line.description or '',  # Using description field if available as notes
                    'amount': line.total_amount,
                })
            
            lines = sorted(lines, key=lambda x: x['date'])

            # Fetch attachments
            attachments = self.env['ir.attachment'].search([
                '|',
                '&', ('res_model', '=', 'hr.expense.sheet'), ('res_id', '=', sheet.id),
                '&', ('res_model', '=', 'hr.expense'), ('res_id', 'in', sheet.expense_line_ids.ids)
            ])
            
            image_attachments = []
            seen_datas = set()
            for att in attachments:
                if att.mimetype and att.mimetype.startswith('image/') and att.datas:
                    if att.datas not in seen_datas:
                        seen_datas.add(att.datas)
                        image_attachments.append({
                            'name': att.name,
                            'data_uri': f"data:{att.mimetype};base64,{att.datas.decode('utf-8')}"
                        })

            report_data.append({
                'doc': sheet,
                'date_str': date_str,
                'lines': lines,
                'total_amount': sum(l['amount'] for l in lines),
                'image_attachments': image_attachments,
            })
            
        return {
            'docs': docs,
            'report_data': report_data,
        }
