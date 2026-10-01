from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

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
    bank_charge_currency_id = fields.Many2one(
        'res.currency', string='Bank Charge Currency',
        default=lambda self: self.env.ref('base.THB'), readonly=True)
    bank_charge_amount = fields.Monetary(
        string='Bank Charges (THB)', currency_field='bank_charge_currency_id', tracking=True,
        help="Bank fee charged on top of the transfer amount. Deducted from the source journal "
             "and booked to the source journal's Extra Bank Charge Account.")
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    payment_id = fields.Many2one('account.payment', string='Payment', readonly=True, copy=False)
    buz_payment_voucher_id = fields.Many2one('account.payment.voucher', string='Payment Voucher', readonly=True, copy=False)
    move_id = fields.Many2one('account.move', string='Journal Entry', related='payment_id.move_id', readonly=True, store=True)
    
    # For report compatibility
    partner_bank_id = fields.Many2one('res.partner.bank', string='Recipient Bank Account', related='destination_journal_id.bank_account_id', readonly=True)
    paired_internal_transfer_payment_id = fields.Many2one('account.payment', related='payment_id.paired_internal_transfer_payment_id', readonly=True)
    ref = fields.Char(string='Memo')

    @api.constrains('bank_charge_amount')
    def _check_bank_charge_amount(self):
        for rec in self:
            if rec.bank_charge_amount < 0:
                raise ValidationError(_("Bank charges cannot be negative."))

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        voucher_id = self._context.get('default_buz_payment_voucher_id') or self._context.get('buz_payment_voucher_id')
        if voucher_id and 'bank_charge_amount' not in vals:
            voucher = self.env['account.payment.voucher'].browse(voucher_id)
            if voucher.exists() and voucher.bank_free_dis:
                vals['bank_charge_amount'] = voucher.bank_free_dis
        return vals

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            company = self.env['res.company'].browse(vals.get('company_id')) if vals.get('company_id') else self.env.company
            vals['name'] = self.env['ir.sequence'].next_by_code_company('account.bank.transfer', company) or '/'
        return super(AccountBankTransfer, self).create(vals)
    
    def action_confirm(self):
        self.ensure_one()
        if self.amount <= 0:
             raise UserError(_("Amount must be strictly positive."))
        if self.journal_id == self.destination_journal_id:
             raise UserError(_("Source and Destination journals must be different."))
        if self.bank_charge_amount > 0 and not self.journal_id.default_bank_charge_account_id:
            raise UserError(_(
                "Please configure the Extra Bank Charge Account on journal '%s' "
                "(Invoicing > Configuration > Journals) before charging a bank fee.",
                self.journal_id.display_name))

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
            'bank_charge_amount': self.bank_charge_amount,
            'bank_charge_currency_id': self.bank_charge_currency_id.id,
        }
        
        if self.buz_payment_voucher_id:
            payment_vals['buz_payment_voucher_id'] = self.buz_payment_voucher_id.id

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
