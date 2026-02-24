from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AccountBankTransfer(models.Model):
    _name = 'account.bank.transfer'
    _description = 'Bank Transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='/', index=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Confirmed'),
        ('cancel', 'Cancelled')
    ], string='Status', required=True, readonly=True, copy=False, tracking=True, default='draft')

    journal_id = fields.Many2one('account.journal', string='Source Journal', required=True, domain=[('type', 'in', ('bank', 'cash'))], tracking=True)
    destination_journal_id = fields.Many2one('account.journal', string='Destination Journal', required=True, domain=[('type', 'in', ('bank', 'cash'))], tracking=True)
    
    amount = fields.Monetary(string='Amount', required=True, tracking=True)
    currency_id = fields.Many2one('res.currency', related='journal_id.currency_id', string='Currency', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)


    payment_id = fields.Many2one('account.payment', string='Payment', readonly=True, copy=False)
    move_id = fields.Many2one('account.move', string='Journal Entry', related='payment_id.move_id', readonly=True, store=True)
    
    # For report compatibility
    partner_bank_id = fields.Many2one('res.partner.bank', string='Recipient Bank Account', related='destination_journal_id.bank_account_id', readonly=True)
    paired_internal_transfer_payment_id = fields.Many2one('account.payment', related='payment_id.paired_internal_transfer_payment_id', readonly=True)
    ref = fields.Char(string='Memo')

    @api.model
    def _get_next_sequence(self, company, seq_date):
        """Get next sequence number for bank transfer, auto-creating company sequence if needed."""
        code = 'account.bank.transfer'
        seq = self.env['ir.sequence'].sudo().with_company(company).next_by_code(code, sequence_date=seq_date)
        if not seq:
            self.env['ir.sequence'].sudo().create({
                'name': 'Bank Transfer - %s' % company.name,
                'code': code,
                'prefix': 'TR%(y)s',
                'padding': 4,
                'company_id': company.id,
            })
            seq = self.env['ir.sequence'].sudo().with_company(company).next_by_code(code, sequence_date=seq_date)
        return seq or '/'

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            company_id = vals.get('company_id') or self.env.company.id
            company = self.env['res.company'].browse(company_id)
            seq_date = vals.get('date') or fields.Date.context_today(self)
            vals['name'] = self._get_next_sequence(company, seq_date)
        return super(AccountBankTransfer, self).create(vals)
    
    def action_confirm(self):
        self.ensure_one()
        if self.amount <= 0:
             raise UserError(_("Amount must be strictly positive."))
        if self.journal_id == self.destination_journal_id:
             raise UserError(_("Source and Destination journals must be different."))
             
        # Create Internal Transfer
        payment_vals = {
            'payment_type': 'outbound',
            'is_internal_transfer': True,
            'journal_id': self.journal_id.id,
            'destination_journal_id': self.destination_journal_id.id,
            'amount': self.amount,
            'date': self.date,
            'ref': self.name + (f" - {self.ref}" if self.ref else ""),
            'currency_id': self.currency_id.id or self.company_id.currency_id.id,
            'company_id': self.company_id.id,
        }
        
        payment = self.env['account.payment'].create(payment_vals)
        payment.action_post()
        
        self.write({
            'state': 'posted',
            'payment_id': payment.id,
        })
        return True

    def action_draft(self):
        for rec in self:
            if rec.payment_id:
                if rec.payment_id.state == 'posted':
                    rec.payment_id.action_draft()
                rec.payment_id.action_cancel()
            rec.write({'state': 'draft'})

    def action_view_payment(self):
        self.ensure_one()
        return {
            'name': _('Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'res_id': self.payment_id.id,
            'view_mode': 'form',
        }
