# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class WeeklyBudgetAllocation(models.Model):
    _name = 'weekly.budget.allocation'
    _description = 'Weekly Budget Allocation'
    _order = 'percentage desc, id'

    plan_id = fields.Many2one(
        'weekly.budget.plan',
        string='Budget Plan',
        required=True,
        ondelete='cascade',
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        required=True,
    )
    percentage = fields.Float(
        string='Percentage (%)',
        required=True,
        default=0.0,
    )
    allocated_amount = fields.Float(
        string='Allocated Amount',
        compute='_compute_allocated_amount',
        store=True,
    )

    @api.depends('percentage', 'plan_id.total_monthly_budget')
    def _compute_allocated_amount(self):
        for rec in self:
            budget = rec.plan_id.total_monthly_budget if rec.plan_id else 0.0
            rec.allocated_amount = budget * (rec.percentage / 100.0)

    @api.constrains('percentage')
    def _check_percentage(self):
        for rec in self:
            if rec.percentage < 0 or rec.percentage > 100:
                raise ValidationError(_("Percentage must be between 0 and 100."))
