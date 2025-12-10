# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AdvanceBoxRefill(models.Model):
    _name = 'advance.box.refill'
    _description = 'Advance Box Refill History'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True,
        readonly=True
    )
    box_id = fields.Many2one(
        'employee.advance.box',
        string='Advance Box',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    amount = fields.Monetary(
        string='Amount',
        required=True,
        currency_field='currency_id',
        tracking=True
    )
    payment_id = fields.Many2one(
        'account.payment',
        string='Payment Transfer',
        readonly=True,
        ondelete='restrict',
        tracking=True
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled')
    ], string='State', default='draft', required=True, tracking=True)
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )
    journal_bank_id = fields.Many2one(
        'account.journal',
        string='Bank Journal',
        domain=[('type', '=', 'bank')],
        tracking=True
    )
    notes = fields.Text(string='Notes')

    @api.depends('box_id', 'date', 'amount')
    def _compute_name(self):
        for record in self:
            if record.box_id and record.date:
                record.name = _('Refill %s - %s') % (record.box_id.name, record.date.strftime('%Y-%m-%d'))
            else:
                record.name = _('New Refill')

    def action_cancel(self):
        """Cancel the refill"""
        for record in self:
            if record.state == 'posted' and record.payment_id:
                raise UserError(_('Cannot cancel a posted refill with payment. Please cancel the payment first.'))
            record.state = 'cancel'

    def action_reset_to_draft(self):
        """Reset to draft"""
        self.write({'state': 'draft'})

    @api.constrains('amount')
    def _check_amount(self):
        for record in self:
            if record.amount <= 0:
                raise UserError(_('Amount must be greater than zero.'))

    def unlink(self):
        """Prevent deletion of posted refills"""
        for record in self:
            if record.state == 'posted':
                raise UserError(_('Cannot delete a posted refill. Please cancel it first.'))
        return super(AdvanceBoxRefill, self).unlink()
