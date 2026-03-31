# -*- coding: utf-8 -*-
from odoo import api, fields, models

class BudgetMove(models.Model):
    _name = 'budget.move'
    _description = 'Budget Move Ledger'
    _order = 'date desc, id desc'

    name = fields.Char(string='Description', required=True)
    
    line_id = fields.Many2one(
        'weekly.budget.line',
        string='Budget Line',
        required=True,
        ondelete='cascade',
        index=True
    )
    plan_id = fields.Many2one(
        related='line_id.plan_id',
        string='Budget Plan',
        store=True,
        index=True
    )
    
    source_model = fields.Selection([
        ('purchase.order', 'Purchase Order'),
        ('employee.purchase.requisition', 'Purchase Requisition'),
        ('material.requisition', 'Material Requisition'),
        ('account.move', 'Vendor Bill')
    ], string='Source Model', required=True)
    
    source_id = fields.Integer(string='Source Record ID', required=True, index=True)
    source_line_id = fields.Integer(string='Source Line ID', index=True, help="Specific document line ID if applicable")
    
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        index=True
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        index=True
    )
    
    amount = fields.Float(string='Amount', required=True)
    move_type = fields.Selection([
        ('reserved', 'Reserved'),
        ('used', 'Used')
    ], string='Type', required=True, index=True)
    
    date = fields.Date(string='Date', required=True, index=True)
    company_id = fields.Many2one(
        related='line_id.company_id',
        string='Company',
        store=True
    )
    currency_id = fields.Many2one(
        related='line_id.currency_id',
        string='Currency',
        store=True
    )

    @api.model
    def _create_move(self, vals):
        """Helper handler for budget movements"""
        return self.create(vals)

    @api.model
    def extract_analytic_distribution(self, line):
        """
        Takes a document line (PO line, Bill line, PR line, MR line)
        and returns a list of dicts:
        [{'analytic_account_id': id, 'department_id': id, 'percentage': float}]
        If no distribution exists, returns fallback.
        """
        res = []
        dist = getattr(line, 'analytic_distribution', False)
        acc_id = getattr(line, 'analytic_account_id', False)
        dept_id = getattr(line, 'department_id', False)
        
        # Identify header to pull fallback department/analytic info
        order = getattr(line, 'order_id', False) or \
                getattr(line, 'requisition_id', False) or \
                getattr(line, 'material_requisition_id', False) or \
                getattr(line, 'requisition_product_id', False)
                
        if order:
            if not acc_id:
                # Some modules use expense_code_id or analytic_account_id
                acc_id = getattr(order, 'analytic_account_id', False) or getattr(order, 'expense_code_id', False)
            if not dept_id:
                dept_id = getattr(order, 'department_id', False) or getattr(order, 'dept_id', False)
        
        if dist:
            for account_id_str, percentage in dist.items():
                for acc_id_piece in str(account_id_str).split(','):
                    if not acc_id_piece.strip():
                        continue
                    acc_int = int(acc_id_piece.strip())
                    res.append({
                        'analytic_account_id': acc_int,
                        'department_id': dept_id.id if hasattr(dept_id, 'id') and dept_id else False,
                        'percentage': percentage / 100.0
                    })
        else:
            res.append({
                'analytic_account_id': acc_id.id if acc_id else False,
                'department_id': dept_id.id if dept_id else False,
                'percentage': 1.0
            })
            
        return res
