# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class MonthlyBudgetAllocation(models.Model):
    _name = 'monthly.budget.allocation'
    _description = 'Monthly Budget Allocation'
    _order = 'percentage desc, id'

    plan_id = fields.Many2one(
        'monthly.budget.plan',
        string='Budget Plan',
        required=True,
        ondelete='cascade',
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        required=True,
    )
    percentage = fields.Float(
        string='Percentage (%)',
        required=True,
        default=0.0,
    )
    amount = fields.Float(
        string='Allocated Amount',
        compute='_compute_amount',
        store=True,
    )
    
    # Active Tracking Fields
    move_ids = fields.One2many(
        'budget.move',
        'allocation_id',
        string='Budget Moves'
    )
    amount_used = fields.Float(
        string='Used Amount',
        compute='_compute_amount_used',
        store=True,
    )
    amount_reserved = fields.Float(
        string='Reserved Amount',
        compute='_compute_amount_reserved',
        store=True,
        help='Tentative budget reserved from non-draft PRs, MRs, and RFQs.',
    )
    forecast_amount = fields.Float(
        string='Forecast Amount',
        compute='_compute_forecast_amount',
        store=True,
    )
    amount_available = fields.Float(
        string='Available (Strict)',
        compute='_compute_remaining',
        store=True,
        help='Allocated Amount minus Used and Reserved.',
    )
    amount_available_forecast = fields.Float(
        string='Available (Forecast)',
        compute='_compute_remaining',
        store=True,
    )
    amount_remaining = fields.Float(
        string='Remaining (vs Used)',
        compute='_compute_remaining',
        store=True,
    )
    usage_percentage = fields.Float(
        string='Usage %',
        compute='_compute_remaining',
        store=True,
    )
    status = fields.Selection([
        ('normal', 'Normal'),
        ('exceeded', 'Exceeded'),
    ], string='Status', compute='_compute_remaining', store=True)

    company_id = fields.Many2one(
        related='plan_id.company_id',
        string='Company',
        store=True,
    )
    all_companies = fields.Boolean(
        related='plan_id.all_companies',
        string='All Companies',
        store=True,
    )
    plan_state = fields.Selection(
        related='plan_id.state',
        string='Plan Status',
        store=True,
    )
    date_from = fields.Date(related='plan_id.date_from', store=True)
    date_to = fields.Date(related='plan_id.date_to', store=True)

    @api.depends('percentage', 'plan_id.total_budget')
    def _compute_amount(self):
        for rec in self:
            budget = rec.plan_id.total_budget if rec.plan_id else 0.0
            rec.amount = budget * (rec.percentage / 100.0)

    @api.constrains('percentage')
    def _check_percentage(self):
        for rec in self:
            if rec.percentage < 0 or rec.percentage > 100:
                raise ValidationError(_("Percentage must be between 0 and 100."))

    @api.depends('move_ids.amount', 'move_ids.move_type')
    def _compute_amount_used(self):
        for line in self:
            line.amount_used = sum(line.move_ids.filtered(lambda m: m.move_type == 'used').mapped('amount'))

    @api.depends('move_ids.amount', 'move_ids.move_type')
    def _compute_amount_reserved(self):
        for line in self:
            line.amount_reserved = sum(line.move_ids.filtered(lambda m: m.move_type == 'reserved').mapped('amount'))

    @api.depends('move_ids.amount', 'move_ids.move_type')
    def _compute_forecast_amount(self):
        for line in self:
            line.forecast_amount = sum(line.move_ids.filtered(lambda m: m.move_type == 'forecast').mapped('amount'))

    @api.depends('amount', 'amount_used', 'amount_reserved', 'forecast_amount')
    def _compute_remaining(self):
        for line in self:
            line.amount_remaining = line.amount - line.amount_used
            line.amount_available = line.amount - line.amount_used - line.amount_reserved
            line.amount_available_forecast = line.amount - line.forecast_amount
            line.usage_percentage = (
                (line.amount_used / line.amount * 100)
                if line.amount else 0.0
            )
            line.status = 'exceeded' if line.amount_used > line.amount else 'normal'

    def action_adjust_budget(self):
        """Open the budget adjustment wizard."""
        self.ensure_one()
        return {
            'name': _('Adjust Budget Allowance'),
            'type': 'ir.actions.act_window',
            'res_model': 'budget.adjustment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_monthly_allocation_id': self.id,
                'default_current_amount': self.amount,
            },
        }

    def _invalidate_reserved(self):
        self.invalidate_recordset(['amount_reserved'])
        self._compute_amount_reserved()
