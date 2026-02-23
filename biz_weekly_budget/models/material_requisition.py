# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MaterialRequisition(models.Model):
    _inherit = 'material.requisition'

    budget_check_result = fields.Html(
        string='Budget Check Result',
        compute='_compute_budget_check_result',
    )

    def _find_budget_line_for_date(self, target_date):
        """Find the confirmed budget line that covers the given date."""
        domain = [
            ('plan_state', '=', 'confirmed'),
            ('date_from', '<=', target_date),
            ('date_to', '>=', target_date),
        ]
        company_domain = [
            '|',
            ('all_companies', '=', True),
            ('company_id', '=', self.company_id.id),
        ]
        budget_lines = self.env['weekly.budget.line'].sudo().search(
            domain + company_domain, limit=1
        )
        return budget_lines[:1] if budget_lines else False

    @api.depends('line_ids.total_cost', 'required_date')
    def _compute_budget_check_result(self):
        for req in self:
            target_date = req.required_date
            if not target_date or not req.line_ids:
                req.budget_check_result = ''
                continue

            budget_line = req._find_budget_line_for_date(target_date)
            if not budget_line:
                req.budget_check_result = _(
                    '<div class="alert alert-info">'
                    'No active weekly budget plan found for the required date.'
                    '</div>'
                )
                continue

            mr_amount = req.total_cost or sum(req.line_ids.mapped('total_cost'))
            used = budget_line.amount_used
            limit_amt = budget_line.amount_limit
            total_after = used + mr_amount
            remaining = limit_amt - total_after
            is_over = remaining < 0

            if is_over:
                status_class = 'danger'
                status_icon = '&#10060;'
                status_text = _('Exceeded!')
            else:
                status_class = 'success'
                status_icon = '&#9989;'
                status_text = _('OK')

            req.budget_check_result = (
                '<div class="card mb-2 border-%s">'
                '<div class="card-body p-2">'
                '<h6 class="card-title">%s %s (MR - Estimate)</h6>'
                '<table class="table table-sm table-borderless mb-0">'
                '<tr><td>%s</td><td class="text-end">%s</td></tr>'
                '<tr><td>%s</td><td class="text-end">%s</td></tr>'
                '<tr><td>%s</td><td class="text-end">%s</td></tr>'
                '<tr class="border-top"><td><strong>%s</strong></td>'
                '<td class="text-end"><strong>%s</strong></td></tr>'
                '<tr><td><strong>%s</strong></td>'
                '<td class="text-end text-%s"><strong>%s %s</strong></td></tr>'
                '</table>'
                '</div></div>' % (
                    status_class,
                    status_icon,
                    budget_line.name,
                    _('Weekly Budget'),
                    '{:,.2f}'.format(limit_amt),
                    _('Already Used (Confirmed POs)'),
                    '{:,.2f}'.format(used),
                    _('This MR Amount (Estimate)'),
                    '{:,.2f}'.format(mr_amount),
                    _('Total (Estimate)'),
                    '{:,.2f}'.format(total_after),
                    _('Remaining (Estimate)'),
                    status_class,
                    '{:,.2f}'.format(remaining),
                    status_text,
                )
            )

    def action_check_budget(self):
        """Button action to trigger budget check recomputation."""
        self.ensure_one()
        self._compute_budget_check_result()
        return True

    def action_submit(self):
        """Override to check weekly budget before submitting."""
        for req in self:
            req._check_weekly_budget()
        return super().action_submit()

    def _check_weekly_budget(self):
        """Check if this MR would exceed any weekly budget."""
        self.ensure_one()
        target_date = self.required_date
        if not target_date or not self.line_ids:
            return

        budget_line = self._find_budget_line_for_date(target_date)
        if not budget_line:
            return  # No budget plan active, allow submission

        mr_amount = self.total_cost or sum(self.line_ids.mapped('total_cost'))
        used = budget_line.amount_used
        limit_amt = budget_line.amount_limit
        total_after = used + mr_amount
        overage = total_after - limit_amt

        if overage > 0:
            # Post to budget plan chatter
            budget_line.plan_id.message_post(
                body=_(
                    '<strong>Budget Exceeded Alert (MR)</strong><br/>'
                    'MR: <strong>%s</strong><br/>'
                    'User: %s<br/>'
                    'Week: %s<br/>'
                    'Budget: %s | Used: %s | MR Amount: %s | Over by: %s'
                ) % (
                    self.name,
                    self.env.user.name,
                    budget_line.name,
                    '{:,.2f}'.format(limit_amt),
                    '{:,.2f}'.format(used),
                    '{:,.2f}'.format(mr_amount),
                    '{:,.2f}'.format(overage),
                ),
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )

            raise UserError(_(
                'Weekly Budget Exceeded! Cannot submit Material Requisition.\n\n'
                'Week: %s\n'
                '  - Budget Limit: %s\n'
                '  - Already Used: %s\n'
                '  - This MR: %s\n'
                '  - Over by: %s'
            ) % (
                budget_line.name,
                '{:,.2f}'.format(limit_amt),
                '{:,.2f}'.format(used),
                '{:,.2f}'.format(mr_amount),
                '{:,.2f}'.format(overage),
            ))
