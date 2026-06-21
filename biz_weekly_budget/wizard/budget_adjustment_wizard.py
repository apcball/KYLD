# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class BudgetAdjustmentWizard(models.TransientModel):
    _name = 'budget.adjustment.wizard'
    _description = 'Budget Adjustment Wizard'

    monthly_allocation_id = fields.Many2one(
        'monthly.budget.allocation',
        string='Budget Allocation',
        required=True,
        readonly=True,
    )
    current_amount = fields.Float(
        string='Current Budget',
        readonly=True,
    )
    new_amount = fields.Float(
        string='New Budget',
        required=True,
    )
    reason = fields.Text(
        string='Reason',
    )

    @api.constrains('reason')
    def _check_reason(self):
        for rec in self:
            if not rec.reason or not rec.reason.strip():
                raise ValidationError(_('Please provide a reason for the adjustment.'))

    def action_confirm(self):
        """Apply the budget adjustment."""
        self.ensure_one()
        if self.new_amount < 0:
            raise UserError(_('New budget amount cannot be negative.'))

        alloc = self.monthly_allocation_id
        old_amount = alloc.amount

        # Update the budget allocation amount directly (if needed, disconnect from percentage)
        alloc.amount = self.new_amount

        # Post message on the plan's chatter
        msg_body = _(
            '<strong>Budget Adjusted</strong><br/>'
            'Department: %s<br/>'
            'Previous: %s<br/>'
            'New: %s<br/>'
            'By: %s<br/>'
            'Reason: %s'
        ) % (
            alloc.department_id.sudo().name or 'Base',
            '{:,.2f}'.format(old_amount),
            '{:,.2f}'.format(self.new_amount),
            self.env.user.name,
            self.reason,
        )

        alloc.plan_id.message_post(
            body=msg_body,
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )

        return {'type': 'ir.actions.act_window_close'}
