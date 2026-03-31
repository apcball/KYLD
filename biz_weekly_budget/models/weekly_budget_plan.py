# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class WeeklyBudgetPlan(models.Model):
    _name = 'weekly.budget.plan'
    _description = 'Weekly Budget Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )
    @api.model
    def _get_year_selection(self):
        current_year = fields.Date.today().year
        return [(str(y), str(y)) for y in range(current_year - 5, current_year + 5)]

    month = fields.Selection([
        ('01', 'January'), ('02', 'February'), ('03', 'March'),
        ('04', 'April'), ('05', 'May'), ('06', 'June'),
        ('07', 'July'), ('08', 'August'), ('09', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December')
    ], string='Month', required=True, tracking=True, default=lambda self: str(fields.Date.today().month).zfill(2))

    year = fields.Selection(
        selection='_get_year_selection',
        string='Year',
        required=True,
        tracking=True,
        default=lambda self: str(fields.Date.today().year),
    )
    date_from = fields.Date(
        string='Date From',
        compute='_compute_dates',
        store=True,
        tracking=True,
    )
    date_to = fields.Date(
        string='Date To',
        compute='_compute_dates',
        store=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        help='Leave empty for All Companies scope',
        tracking=True,
    )
    all_companies = fields.Boolean(
        string='All Companies',
        default=False,
        tracking=True,
        help='If checked, budget applies to all companies',
    )
    default_weekly_amount = fields.Float(
        string='Default Weekly Amount',
        tracking=True,
        help="Fallback amount if no allocations are defined",
    )
    total_monthly_budget = fields.Float(
        string='Total Budget (Plan)',
        tracking=True,
        help="Total budget for this entire period. Allocations are distributed based on this parameter."
    )
    allocation_ids = fields.One2many(
        'weekly.budget.allocation',
        'plan_id',
        string='Analytic Allocations',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    notify_user_ids = fields.Many2many(
        'res.users',
        'weekly_budget_plan_notify_user_rel',
        'plan_id',
        'user_id',
        string='Notify Users',
        help='Users to notify when budget is exceeded',
    )
    line_ids = fields.One2many(
        'weekly.budget.line',
        'plan_id',
        string='Weekly Budget Lines',
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, copy=False)

    # Summary fields
    total_budget = fields.Float(
        string='Total Budget',
        compute='_compute_totals',
        store=True,
    )
    total_used = fields.Float(
        string='Total Used',
        compute='_compute_totals',
        store=True,
    )
    total_remaining = fields.Float(
        string='Total Remaining',
        compute='_compute_totals',
        store=True,
    )
    usage_percentage = fields.Float(
        string='Usage %',
        compute='_compute_totals',
        store=True,
    )

    @api.depends('year', 'month')
    def _compute_dates(self):
        for rec in self:
            if rec.year and rec.month:
                start_date = fields.Date.from_string(f"{rec.year}-{rec.month}-01")
                rec.date_from = start_date
                
                if int(rec.month) == 12:
                    next_month = start_date.replace(year=start_date.year + 1, month=1, day=1)
                else:
                    next_month = start_date.replace(month=start_date.month + 1, day=1)
                rec.date_to = next_month - timedelta(days=1)
            else:
                rec.date_from = False
                rec.date_to = False

    @api.depends('line_ids.amount_limit', 'line_ids.amount_used')
    def _compute_totals(self):
        for rec in self:
            rec.total_budget = sum(rec.line_ids.mapped('amount_limit'))
            rec.total_used = sum(rec.line_ids.mapped('amount_used'))
            rec.total_remaining = rec.total_budget - rec.total_used
            rec.usage_percentage = (
                (rec.total_used / rec.total_budget * 100)
                if rec.total_budget else 0.0
            )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_('Date From must be before Date To.'))

    @api.constrains('all_companies', 'company_id')
    def _check_company_scope(self):
        for rec in self:
            if not rec.all_companies and not rec.company_id:
                raise ValidationError(
                    _('Please select a Company or check "All Companies".')
                )

    @api.onchange('all_companies')
    def _onchange_all_companies(self):
        if self.all_companies:
            self.company_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'weekly.budget.plan'
                ) or _('New')
        return super().create(vals_list)

    def action_generate_weeks(self):
        """Generate weekly budget lines from date_from to date_to (Mon-Sun).
           If allocation_ids exist, distribute evenly across generated weeks.
        """
        for rec in self:
            if not rec.date_from or not rec.date_to:
                raise UserError(_('Please set Date From and Date To first.'))

            # Remove existing draft lines that haven't been used or reserved
            rec.line_ids.filtered(lambda l: l.amount_used == 0 and l.amount_reserved == 0).unlink()

            # Find the Monday on or before date_from
            start = rec.date_from
            # weekday(): Monday=0, Sunday=6
            monday_start = start - timedelta(days=start.weekday())

            weeks_list = []
            monday = monday_start
            week_num = 1
            while monday <= rec.date_to:
                weeks_list.append({
                    'monday': monday,
                    'sunday': monday + timedelta(days=6),
                    'num': week_num
                })
                monday += timedelta(days=7)
                week_num += 1

            total_weeks = len(weeks_list)
            if total_weeks == 0:
                continue

            if rec.allocation_ids:
                for alloc in rec.allocation_ids:
                    weekly_amount = alloc.allocated_amount / total_weeks if total_weeks > 0 else 0
                    
                    for w in weeks_list:
                        week_label = 'W%d (%s - %s)' % (
                            w['num'],
                            w['monday'].strftime('%d/%m'),
                            w['sunday'].strftime('%d/%m'),
                        )
                        existing = rec.line_ids.filtered(
                            lambda l, a=alloc, mon=w['monday'], sun=w['sunday']: 
                            l.date_from == mon and l.date_to == sun and 
                            l.analytic_account_id == a.analytic_account_id and 
                            (l.department_id == a.department_id)
                        )
                        if not existing:
                            self.env['weekly.budget.line'].create({
                                'plan_id': rec.id,
                                'name': week_label,
                                'week_number': w['num'],
                                'date_from': w['monday'],
                                'date_to': w['sunday'],
                                'amount_limit': weekly_amount,
                                'analytic_account_id': alloc.analytic_account_id.id,
                                'department_id': alloc.department_id.id if alloc.department_id else False,
                            })
            else:
                for w in weeks_list:
                    week_label = 'W%d (%s - %s)' % (
                        w['num'],
                        w['monday'].strftime('%d/%m'),
                        w['sunday'].strftime('%d/%m'),
                    )
                    existing = rec.line_ids.filtered(
                        lambda l, mon=w['monday'], sun=w['sunday']: 
                        l.date_from == mon and l.date_to == sun and 
                        not l.analytic_account_id
                    )
                    if not existing:
                        self.env['weekly.budget.line'].create({
                            'plan_id': rec.id,
                            'name': week_label,
                            'week_number': w['num'],
                            'date_from': w['monday'],
                            'date_to': w['sunday'],
                            'amount_limit': rec.default_weekly_amount,
                        })

    def action_confirm(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(
                    _('Please generate weekly budget lines before confirming.')
                )
            rec.state = 'confirmed'

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_recompute_used(self):
        """Legacy helper now redirects to global budget recompute."""
        self.action_recompute_all_budgets()

    @api.model
    def action_recompute_all_budgets(self):
        """Global sweep to rebuild all budget_move records across all plans."""
        self.env['budget.move'].search([]).unlink()
        self.env['employee.purchase.requisition'].search([('state', '!=', 'draft')])._update_budget_moves()
        self.env['material.requisition'].search([('state', '!=', 'draft')])._update_budget_moves()
        self.env['purchase.order'].search([('state', '!=', 'cancel')])._update_budget_moves()
        self.env['account.move'].search([('state', '=', 'posted'), ('move_type', 'in', ('in_invoice', 'in_refund'))])._update_budget_moves()
