# -*- coding: utf-8 -*-
import logging
from datetime import timedelta
from odoo.tools import float_compare

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class MonthlyBudgetPlan(models.Model):
    _name = 'monthly.budget.plan'
    _description = 'Monthly Budget Plan'
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
        default=lambda self: self.env.company,
        tracking=True,
    )
    all_companies = fields.Boolean(
        string='All Companies',
        default=False,
        tracking=True,
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )

    total_budget = fields.Float(
        string='Total Budget',
        tracking=True,
        required=True,
        help="Total budget for this month. Allocations are distributed based on this parameter."
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, copy=False)

    allocation_ids = fields.One2many(
        'monthly.budget.allocation',
        'plan_id',
        string='Department Allocations',
    )
    notify_user_ids = fields.Many2many(
        'res.users',
        'monthly_budget_plan_notify_rel',
        'plan_id',
        'user_id',
        string='Notify on Budget Exceeded',
        help='Users notified by email when a budget violation occurs on this plan.',
    )

    # Summary fields
    total_used = fields.Float(
        string='Total Used',
        compute='_compute_totals',
        store=True,
    )
    total_reserved = fields.Float(
        string='Total Reserved',
        compute='_compute_totals',
        store=True,
    )
    total_forecast = fields.Float(
        string='Total Forecast',
        compute='_compute_totals',
        store=True,
    )
    total_remaining = fields.Float(
        string='Available Budget',
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

    @api.depends('allocation_ids.amount_used', 'allocation_ids.amount_reserved', 'allocation_ids.forecast_amount')
    def _compute_totals(self):
        for rec in self:
            rec.total_used = sum(rec.allocation_ids.mapped('amount_used'))
            rec.total_reserved = sum(rec.allocation_ids.mapped('amount_reserved'))
            rec.total_forecast = sum(rec.allocation_ids.mapped('forecast_amount'))
            rec.total_remaining = rec.total_budget - rec.total_used - rec.total_reserved
            rec.usage_percentage = (
                ((rec.total_used + rec.total_reserved) / rec.total_budget * 100)
                if rec.total_budget else 0.0
            )

    @api.constrains('all_companies', 'company_id')
    def _check_company_scope(self):
        for rec in self:
            if not rec.all_companies and not rec.company_id:
                raise ValidationError(_('Please select a Company or check "All Companies".'))

    @api.onchange('all_companies')
    def _onchange_all_companies(self):
        if self.all_companies:
            self.company_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('monthly.budget.plan') or _('New')
        return super().create(vals_list)

    def action_confirm(self):
        for rec in self:
            if not rec.allocation_ids:
                raise UserError(_('Please configure department allocations before confirming.'))
            total_alloc = sum(rec.allocation_ids.mapped('amount'))
            # Fix: Use float_compare instead of round for precision issues
            if float_compare(total_alloc, rec.total_budget, precision_digits=2) != 0:
                raise UserError(_('Total allocations must equal the total budget.'))
            rec.state = 'confirmed'

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_recompute_all_budgets(self):
        """Rebuild budget_move records for THIS plan only (not all plans).

        Deletes only the moves linked to this plan's allocations and
        reprocesses documents whose payment/bill dates fall within
        the plan's date range.
        """
        self.ensure_one()
        if not self.date_from or not self.date_to:
            raise UserError(_('Plan date range is not set.'))

        ctx = dict(
            self.env.context,
            _skip_trigger_linked=True,
            _budget_allocation_cache={},
        )
        self = self.with_context(**ctx)

        # Delete only moves belonging to this plan
        plan_allocs = self.allocation_ids
        self.env['budget.move'].sudo().search([
            ('allocation_id', 'in', plan_allocs.ids)
        ]).unlink()

        date_from, date_to = self.date_from, self.date_to

        steps = [
            ('employee.purchase.requisition', 'payment_date',
             [('state', '!=', 'draft')]),
            ('material.requisition', 'payment_date',
             [('state', '!=', 'draft')]),
            ('purchase.order', 'payment_date',
             [('state', '!=', 'cancel')]),
            ('account.move', 'invoice_date_due',
             [('state', 'in', ('draft', 'posted')),
              ('move_type', 'in', ('in_invoice', 'in_refund'))]),
        ]
        for model_name, date_field, base_domain in steps:
            domain = base_domain + [
                (date_field, '>=', date_from),
                (date_field, '<=', date_to),
            ]
            records = self.env[model_name].sudo().search(domain)
            if records:
                records._update_budget_moves()

        # Re-read to show fresh computed fields
        self.invalidate_recordset(['total_used', 'total_reserved', 'total_remaining', 'usage_percentage'])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Recomputation Complete'),
                'message': _('Budget moves for %s have been rebuilt.') % self.name,
                'type': 'success',
                'sticky': True,
            }
        }

    @api.model
    def _cron_recompute_all_budgets(self):
        """Global sweep to rebuild all budget_move records. Executed by cron.

        Strategy:
        - Delete ALL budget moves at the start (catches orphaned records).
        - Rebuild atomically so an error cannot leave the ledger partially empty.
        - Skip linked-doc triggers (PO↔PR/MR, bill↔PO) because the cron
          processes every doc once per step anyway.
        - Pre-populate an allocation cache so the thousands of per-line
          _get_allocation calls resolve from memory instead of hitting the DB.
        """
        ctx = dict(
            self.env.context,
            _skip_trigger_linked=True,
            _budget_allocation_cache={},
        )
        self = self.with_context(**ctx)

        self.env['budget.move'].sudo().search([]).unlink()

        steps = [
            ('employee.purchase.requisition', [('state', '!=', 'draft')]),
            ('material.requisition', [('state', '!=', 'draft')]),
            ('purchase.order', [('state', '!=', 'cancel')]),
            ('account.move', [('state', 'in', ('draft', 'posted')),
                              ('move_type', 'in', ('in_invoice', 'in_refund'))]),
        ]
        for model_name, domain in steps:
            records = self.env[model_name].sudo().search(domain)
            if records:
                records._update_budget_moves()
