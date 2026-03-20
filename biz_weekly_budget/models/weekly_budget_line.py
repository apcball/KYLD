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
    amount_limit = fields.Float(string='Budget Limit', required=True)
    amount_used = fields.Float(
        string='Used Amount',
        compute='_compute_amount_used',
        store=True,
    )
    amount_remaining = fields.Float(
        string='Remaining',
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

    @api.depends('date_from', 'date_to', 'plan_id.company_id',
                 'plan_id.all_companies', 'plan_id.state')
    def _compute_amount_used(self):
        """Compute total confirmed PO amount for this week's date range."""
        for line in self:
            if not line.date_from or not line.date_to:
                line.amount_used = 0.0
                continue

            domain = [
                ('state', 'in', ['purchase', 'done']),
            ]

            # Company scope
            if line.plan_id.all_companies:
                pass  # No company filter
            elif line.plan_id.company_id:
                domain.append(('company_id', '=', line.plan_id.company_id.id))

            # Find PO lines where date_planned falls within this week
            po_line_domain = [
                ('order_id.state', 'in', ['purchase', 'done']),
                ('date_planned', '>=', fields.Datetime.to_datetime(line.date_from)),
                ('date_planned', '<=', fields.Datetime.to_datetime(
                    line.date_to).replace(hour=23, minute=59, second=59)),
            ]

            if line.plan_id.all_companies:
                pass
            elif line.plan_id.company_id:
                po_line_domain.append(
                    ('order_id.company_id', '=', line.plan_id.company_id.id)
                )

            po_lines = self.env['purchase.order.line'].sudo().search(po_line_domain)
            line.amount_used = sum(po_lines.mapped('price_subtotal'))

    @api.depends('amount_limit', 'amount_used')
    def _compute_remaining(self):
        for line in self:
            line.amount_remaining = line.amount_limit - line.amount_used
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
