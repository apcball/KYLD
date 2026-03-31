# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _find_budget_lines_for_date(env, target_date, company_id):
    """Helper: find confirmed budget lines covering target_date."""
    if not target_date:
        return env['weekly.budget.line']
    domain = [
        ('plan_state', '=', 'confirmed'),
        ('date_from', '<=', target_date),
        ('date_to', '>=', target_date),
        '|',
        ('all_companies', '=', True),
        ('company_id', '=', company_id),
    ]
    return env['weekly.budget.line'].sudo().search(domain)


class EmployeePurchaseRequisition(models.Model):
    _inherit = 'employee.purchase.requisition'

    payment_date = fields.Date(
        string='Expected Payment',
        compute='_compute_payment_date',
        store=True,
        readonly=False,
        help="Expected date of cash outflow. Default is Requisition Deadline + 30 days."
    )

    budget_check_result = fields.Html(
        string='Budget Check Result',
        compute='_compute_budget_check_result',
    )

    buz_budget_approval_id = fields.Many2one(
        'buz.budget.approval.request',
        string='Budget Approval Request',
        compute='_compute_budget_approval_id',
        store=False,
    )
    buz_budget_approval_state = fields.Selection(
        related='buz_budget_approval_id.state',
        string='Budget Approval Status',
    )
    budget_warning = fields.Boolean(
        string='Budget Warning',
        compute='_compute_budget_check_result'
    )

    def _compute_budget_approval_id(self):
        ApprovalReq = self.env['buz.budget.approval.request'].sudo()
        for rec in self:
            req = ApprovalReq.search([
                ('document_type', '=', 'pr'),
                ('ref_pr_id', '=', rec.id),
            ], limit=1, order='id desc')
            rec.buz_budget_approval_id = req

    @api.depends('requisition_deadline', 'request_date')
    def _compute_payment_date(self):
        for req in self:
            if req.payment_date:
                continue
            base_date = req.requisition_deadline or req.request_date or fields.Date.today()
            req.payment_date = base_date + timedelta(days=30)

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

    def write(self, vals):
        """Trigger budget reserved moves recompute when state or payment_date changes."""
        res = super().write(vals)
        if 'state' in vals or 'payment_date' in vals:
            self._update_budget_moves()
        return res

    def _clear_budget_moves(self):
        BudgetMove = self.env['budget.move'].sudo()
        for req in self:
            moves = BudgetMove.search([('source_model', '=', 'employee.purchase.requisition'), ('source_id', '=', req.id)])
            if moves:
                moves.unlink()

    def _update_budget_moves(self):
        self._clear_budget_moves()
        BudgetMove = self.env['budget.move'].sudo()
        BudgetLine = self.env['weekly.budget.line'].sudo()
        
        for req in self.filtered(lambda r: r.state != 'draft'):
            # Skip if linked to confirmed PO
            confirmed_pos = self.env['purchase.order'].sudo().search([
                ('state', 'in', ('purchase', 'done')),
                '|', ('requisition_order', '=', req.name),
                     ('pr_number', '=', req.name)
            ], limit=1)
            
            if confirmed_pos:
                continue
                
            budget_date = req.payment_date
            if not budget_date:
                continue
                
            for line in req.requisition_order_ids:
                amount = line.price_subtotal
                dists = BudgetMove.extract_analytic_distribution(line)
                for dist in dists:
                    dist_amount = amount * dist['percentage']
                    if dist_amount == 0: continue
                    
                    bline = BudgetLine.search([
                        ('plan_state', '=', 'confirmed'),
                        ('date_from', '<=', budget_date),
                        ('date_to', '>=', budget_date),
                        ('analytic_account_id', '=', dist['analytic_account_id']),
                        ('department_id', '=', dist['department_id']),
                        '|', ('all_companies', '=', True), ('company_id', '=', req.company_id.id),
                    ], limit=1)
                    if not bline:
                        bline = BudgetLine.search([
                            ('plan_state', '=', 'confirmed'),
                            ('date_from', '<=', budget_date),
                            ('date_to', '>=', budget_date),
                            ('analytic_account_id', '=', False),
                            ('department_id', '=', False),
                            '|', ('all_companies', '=', True), ('company_id', '=', req.company_id.id),
                        ], limit=1)
                    if bline:
                        BudgetMove.create({
                            'name': f"{req.name} - {line.product_id.name or 'Line'}",
                            'line_id': bline.id,
                            'source_model': 'employee.purchase.requisition',
                            'source_id': req.id,
                            'source_line_id': line.id,
                            'analytic_account_id': dist['analytic_account_id'],
                            'department_id': dist['department_id'],
                            'amount': dist_amount,
                            'move_type': 'reserved',
                            'date': budget_date,
                        })

    @api.depends('requisition_order_ids.price_subtotal', 'payment_date')
    def _compute_budget_check_result(self):
        for req in self:
            target_date = req.payment_date
            if not target_date or not req.requisition_order_ids:
                req.budget_check_result = ''
                req.budget_warning = False
                continue

            budget_line = req._find_budget_line_for_date(target_date)
            if not budget_line:
                req.budget_check_result = _(
                    '<div class="alert alert-info">'
                    'No active weekly budget plan found for the expected payment date.'
                    '</div>'
                )
                req.budget_warning = False
                continue

            pr_amount = sum(req.requisition_order_ids.mapped('price_subtotal'))
            used = budget_line.amount_used
            reserved = budget_line.amount_reserved
            limit_amt = budget_line.amount_limit
            total_after = used + reserved + pr_amount
            remaining = limit_amt - total_after
            is_over = remaining < 0

            req.budget_warning = is_over

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
                '<h6 class="card-title">%s %s (PR - Estimate)</h6>'
                '<table class="table table-sm table-borderless mb-0">'
                '<tr><td>%s</td><td class="text-end">%s</td></tr>'
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
                    _('Already Reserved (Other PR/MR/RFQ)'),
                    '{:,.2f}'.format(reserved),
                    _('This PR Amount (Estimate)'),
                    '{:,.2f}'.format(pr_amount),
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

    def action_request_budget_approval(self):
        """Submit a budget approval request when budget is exceeded."""
        self.ensure_one()
        target_date = self.payment_date
        budget_line = self._find_budget_line_for_date(target_date) if target_date else False
        pr_amount = sum(self.requisition_order_ids.mapped('price_subtotal'))

        used = budget_line.amount_used if budget_line else 0.0
        reserved = budget_line.amount_reserved if budget_line else 0.0
        limit_amt = budget_line.amount_limit if budget_line else 0.0
        overage = max(0.0, used + reserved + pr_amount - limit_amt)

        return {
            'name': _('Request Budget Approval'),
            'type': 'ir.actions.act_window',
            'res_model': 'budget.request.reason.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_document_type': 'pr',
                'default_ref_id': self.id,
                'default_budget_line_id': budget_line.id if budget_line else False,
                'default_amount_requested': pr_amount,
                'default_amount_used': used,
                'default_amount_reserved': reserved,
                'default_amount_limit': limit_amt,
                'default_amount_overage': overage,
            }
        }

    def action_confirm_requisition(self):
        """Override to check weekly budget before submitting PR."""
        for req in self:
            req._check_weekly_budget()
        return super().action_confirm_requisition()

    def action_head_approval(self):
        """Override to check weekly budget before head approval."""
        for req in self:
            req._check_weekly_budget()
        return super().action_head_approval()

    def _check_weekly_budget(self):
        """Check if this PR would exceed any weekly budget."""
        self.ensure_one()
        target_date = self.payment_date
        if not target_date or not self.requisition_order_ids:
            return

        # Check if an approved budget request exists
        approved = self.env['buz.budget.approval.request'].sudo().search([
            ('document_type', '=', 'pr'),
            ('ref_pr_id', '=', self.id),
            ('state', '=', 'approved'),
        ], limit=1)
        if approved:
            return  # Bypass budget check – approved

        budget_line = self._find_budget_line_for_date(target_date)
        if not budget_line:
            return  # No budget plan active, allow approval

        pr_amount = sum(self.requisition_order_ids.mapped('price_subtotal'))
        used = budget_line.amount_used
        reserved = budget_line.amount_reserved
        limit_amt = budget_line.amount_limit
        total_after = used + reserved + pr_amount
        overage = total_after - limit_amt

        if overage > 0:
            # Post to budget plan chatter
            budget_line.plan_id.message_post(
                body=_(
                    '<strong>Budget Exceeded Alert (PR)</strong><br/>'
                    'PR: <strong>%s</strong><br/>'
                    'User: %s<br/>'
                    'Week: %s<br/>'
                    'Budget: %s | Used: %s | Reserved: %s | PR Amount: %s | Over by: %s'
                ) % (
                    self.name,
                    self.env.user.name,
                    budget_line.name,
                    '{:,.2f}'.format(limit_amt),
                    '{:,.2f}'.format(used),
                    '{:,.2f}'.format(reserved),
                    '{:,.2f}'.format(pr_amount),
                    '{:,.2f}'.format(overage),
                ),
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )

            raise UserError(_(
                'Weekly Budget Exceeded! Cannot approve Purchase Requisition.\n\n'
                'Week: %s\n'
                '  - Budget Limit: %s\n'
                '  - Already Used: %s\n'
                '  - Already Reserved: %s\n'
                '  - This PR: %s\n'
                '  - Over by: %s\n\n'
                'Please click "ขอเพิ่มงบประมาณ" to submit a Budget Approval Request.'
            ) % (
                budget_line.name,
                '{:,.2f}'.format(limit_amt),
                '{:,.2f}'.format(used),
                '{:,.2f}'.format(reserved),
                '{:,.2f}'.format(pr_amount),
                '{:,.2f}'.format(overage),
            ))
