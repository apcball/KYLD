# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class WeeklyBudgetLine(models.Model):
    _name = 'weekly.budget.line'
    _description = 'Weekly Budget Line'
    _order = 'date_from asc'

    plan_id = fields.Many2one(
        'weekly.budget.plan',
        string='Budget Plan',
        required=True,
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(string='Week Label', required=True)
    week_number = fields.Integer(string='Week #')
    date_from = fields.Date(string='Date From', required=True, index=True)
    date_to = fields.Date(string='Date To', required=True, index=True)
    
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', index=True)
    department_id = fields.Many2one('hr.department', string='Department', index=True)
    
    move_ids = fields.One2many('budget.move', 'line_id', string='Budget Moves')
    
    amount_limit = fields.Float(string='Budget Limit', required=True)
    amount_used = fields.Float(
        string='Used Amount',
        compute='_compute_amount_used',
        store=True,
    )
    amount_reserved = fields.Float(
        string='Reserved Amount',
        compute='_compute_amount_reserved',
        store=True,
        help='Total tentative budget reserved from non-draft PRs, MRs, and standalone RFQs.',
    )
    amount_available = fields.Float(
        string='Available',
        compute='_compute_remaining',
        store=True,
        help='Budget Limit minus Used and Reserved amounts.',
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

    currency_id = fields.Many2one(
        related='plan_id.currency_id',
        string='Currency',
        store=True,
    )
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

    # History tracking
    history_ids = fields.One2many(
        'weekly.budget.line.history',
        'line_id',
        string='Adjustment History',
    )

    def _get_company_domain(self):
        """Return company domain filter for this budget line."""
        if self.plan_id.all_companies:
            return []
        elif self.plan_id.company_id:
            return [('company_id', '=', self.plan_id.company_id.id)]
        return []

    @api.depends('move_ids.amount', 'move_ids.move_type')
    def _compute_amount_used(self):
        """Compute used amount from budget moves."""
        for line in self:
            line.amount_used = sum(line.move_ids.filtered(lambda m: m.move_type == 'used').mapped('amount'))

    @api.depends('move_ids.amount', 'move_ids.move_type')
    def _compute_amount_reserved(self):
        """Compute total reserved amount from budget moves."""
        for line in self:
            line.amount_reserved = sum(line.move_ids.filtered(lambda m: m.move_type == 'reserved').mapped('amount'))

    @api.depends('amount_limit', 'amount_used', 'amount_reserved')
    def _compute_remaining(self):
        for line in self:
            line.amount_remaining = line.amount_limit - line.amount_used
            line.amount_available = line.amount_limit - line.amount_used - line.amount_reserved
            line.usage_percentage = (
                (line.amount_used / line.amount_limit * 100)
                if line.amount_limit else 0.0
            )
            line.status = 'exceeded' if line.amount_used > line.amount_limit else 'normal'

    def action_adjust_budget(self):
        """Open the budget adjustment wizard."""
        self.ensure_one()
        return {
            'name': _('Adjust Budget'),
            'type': 'ir.actions.act_window',
            'res_model': 'budget.adjustment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_line_id': self.id,
                'default_current_amount': self.amount_limit,
            },
        }

    def _invalidate_reserved(self):
        """Force recompute of amount_reserved for budget lines covering this date range."""
        self.invalidate_recordset(['amount_reserved'])
        self._compute_amount_reserved()


class WeeklyBudgetLineHistory(models.Model):
    _name = 'weekly.budget.line.history'
    _description = 'Budget Line Adjustment History'
    _order = 'create_date desc'

    line_id = fields.Many2one(
        'weekly.budget.line',
        string='Budget Line',
        required=True,
        ondelete='cascade',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Adjusted By',
        default=lambda self: self.env.uid,
        readonly=True,
    )
    date = fields.Datetime(
        string='Date',
        default=fields.Datetime.now,
        readonly=True,
    )
    old_amount = fields.Float(string='Previous Amount', readonly=True)
    new_amount = fields.Float(string='New Amount', readonly=True)
    reason = fields.Text(string='Reason', readonly=True)
