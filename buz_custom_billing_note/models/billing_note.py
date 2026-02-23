from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from num2words import num2words
import logging

_logger = logging.getLogger(__name__)

class BillingNote(models.Model):
    _name = 'billing.note'
    _description = 'Billing Note'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    _sql_constraints = [
        ('name_uniq', 'unique(name, company_id)', 'Billing note number must be unique per company!'),
    ]

    name = fields.Char(string='Number', readonly=True, copy=False, default='/')
    note_type = fields.Selection([
        ('receivable', 'Customer Invoice'),
        ('payable', 'Vendor Bill')
    ], string='Type', required=True, default='receivable', tracking=True)

    partner_id = fields.Many2one('res.partner', string='Partner', required=True, tracking=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today, tracking=True)
    due_date = fields.Date(string='Due Date', required=True, default=fields.Date.context_today, tracking=True)
    
    invoice_ids = fields.Many2many(
        'account.move', 'billing_note_invoice_rel',
        'billing_note_id', 'invoice_id',
        string='Documents',
        domain="[('id', 'in', available_invoice_ids)]",
        tracking=True
    )
    available_invoice_ids = fields.Many2many(
        'account.move', 'billing_note_available_invoice_rel',
        'billing_note_id', 'invoice_id',
        string='Available Invoices',
        compute='_compute_available_invoices',
        store=True
    )
    
    amount_total = fields.Monetary(string='Total Amount', compute='_compute_amount_total', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    line_ids = fields.One2many('billing.note.line', 'billing_note_id', string='Lines')
    
    notification_sent = fields.Boolean(string='Notification Sent', default=False)
    days_before_due = fields.Integer(string='Days Before Due for Notification', default=7)

    messenger_sent_date = fields.Date(string='วันที่ส่งแมสเซนเจอร์', tracking=True)
    messenger_received_date = fields.Date(string='วันที่รับจากแมสเซนเจอร์', tracking=True)
    ar_sent_date = fields.Date(string='วันที่ส่งบัญชีลูกหนี้', tracking=True)
    ar_received_date = fields.Date(string='วันที่บัญชีลูกหนี้รับ', tracking=True)
    note = fields.Text(string='หมายเหตุ', tracking=True)

    # Related fields for partner information
    partner_vat = fields.Char(string='Tax ID', related='partner_id.vat', store=True, readonly=True)
    partner_address = fields.Char(string='Full Address', compute='_compute_partner_address', store=True, readonly=True)
    partner_phone = fields.Char(string='Phone', related='partner_id.phone', store=True, readonly=True)
    partner_mobile = fields.Char(string='Mobile', related='partner_id.mobile', store=True, readonly=True)
    partner_contact_name = fields.Char(string='Contact Name', compute='_compute_partner_contact_name', store=True, readonly=True)
    partner_delivery_address = fields.Char(string='Delivery Address', compute='_compute_partner_delivery_address', store=True, readonly=True)

    # Related fields for sale order, salesperson, payment term, due date
    sale_order_number = fields.Char(string='Sale Order Number', compute='_compute_sale_order_number', store=True, readonly=True)
    salesperson_id = fields.Many2one('res.users', string='Salesperson', compute='_compute_salesperson', store=True, readonly=True)
    salesperson_name = fields.Char(
        string='Salesperson Name',
        compute='_compute_salesperson_name',
        store=True,
        readonly=True
    )

    @api.depends('salesperson_id')
    def _compute_salesperson_name(self):
        for rec in self:
            # Show employee name if linked, otherwise user name
            employee = self.env['hr.employee'].search([('user_id', '=', rec.salesperson_id.id)], limit=1)
            rec.salesperson_name = employee.name if employee else (rec.salesperson_id.name or '')
            
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Term', compute='_compute_payment_term', store=True, readonly=True)
    invoice_due_date = fields.Date(string='Invoice Due Date', compute='_compute_invoice_due_date', store=True, readonly=True)

    amount_total_words = fields.Char(
        string="จำนวนเงินตัวอักษร",
        compute="_compute_amount_total_words",
        store=True,
        readonly=True,
    )

    @api.depends('amount_total', 'currency_id')
    def _compute_amount_total_words(self):
        for rec in self:
            if rec.amount_total is not None and rec.currency_id:
                amount = "%.2f" % rec.amount_total
                int_part, dec_part = amount.split('.')
                baht = int(int_part)
                satang = int(dec_part)
                # Only use Thai for THB, fallback to English otherwise
                if rec.currency_id.name == 'THB':
                    baht_text = num2words(baht, lang='th').replace('เอ็ดบาท', 'หนึ่งบาท')
                    if satang > 0:
                        satang_text = num2words(satang, lang='th').replace('เอ็ด', 'หนึ่ง')
                        rec.amount_total_words = f"{baht_text}บาท {satang_text}สตางค์"
                    else:
                        rec.amount_total_words = f"{baht_text}บาทถ้วน"
                else:
                    rec.amount_total_words = num2words(rec.amount_total, lang='en').title()
            else:
                rec.amount_total_words = ''

    @api.depends('partner_id')
    def _compute_partner_address(self):
        for rec in self:
            rec.partner_address = rec.partner_id and rec.partner_id.contact_address or ''

    @api.depends('partner_id')
    def _compute_partner_contact_name(self):
        for rec in self:
            # ถ้ามี contact แยก (type=contact) ให้แสดงชื่อแรกสุด ถ้าไม่มีให้ใช้ชื่อ partner หลัก
            contact = rec.partner_id.child_ids.filtered(lambda c: c.type == 'contact')
            rec.partner_contact_name = contact[0].name if contact else (rec.partner_id.name if rec.partner_id else '')

    @api.depends('partner_id')
    def _compute_partner_delivery_address(self):
        for rec in self:
            delivery = rec.partner_id.child_ids.filtered(lambda c: c.type == 'delivery')
            rec.partner_delivery_address = delivery[0].contact_address if delivery else ''

    @api.depends('partner_id', 'note_type', 'company_id')
    def _compute_available_invoices(self):
        """Compute available invoices for selection"""
        for rec in self:
            # Clear the field if no partner is selected
            if not rec.partner_id:
                rec.available_invoice_ids = self.env['account.move']
                continue

            domain = [
                ('partner_id', '=', rec.partner_id.id),
                ('state', '=', 'posted'),
                ('amount_total', '>', 0),
                ('company_id', '=', rec.company_id.id),
            ]
            
            # Only exclude invoices from other billing notes if this is an existing record
            if not rec._origin.id:
                used_invoices = self.env['account.move']
            else:
                used_invoices = self.env['billing.note'].search([
                    ('id', '!=', rec._origin.id),  # Exclude current billing note
                    ('state', 'in', ['confirm', 'done']),  # Only consider confirmed/done billing notes
                    ('company_id', '=', rec.company_id.id),  # Only from same company
                ]).mapped('invoice_ids')
                if used_invoices:
                    domain.append(('id', 'not in', used_invoices.ids))  # Exclude invoices already in other billing notes
            
            if rec.note_type == 'receivable':
                domain.extend([
                    ('move_type', '=', 'out_invoice'),
                ])
            else:
                domain.extend([
                    ('move_type', '=', 'in_invoice'),
                ])
            
            rec.available_invoice_ids = self.env['account.move'].search(domain)

    @api.depends('invoice_ids', 'invoice_ids.amount_total')
    def _compute_amount_total(self):
        """Compute total amount from invoices"""
        for rec in self:
            # Use amount_total to show actual total amount of invoices
            rec.amount_total = sum(rec.invoice_ids.mapped('amount_total'))

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            company_id = vals.get('company_id') or self.env.company.id
            company = self.env['res.company'].browse(company_id)
            # Get the correct sequence code based on note type
            if vals.get('note_type') == 'receivable':
                sequence_code = 'customer.billing.note'
            else:
                sequence_code = 'vendor.billing.note'
            vals['name'] = self.env['ir.sequence'].with_company(company_id).next_by_code(sequence_code) or '/'
        return super(BillingNote, self).create(vals)

    @api.onchange('invoice_ids')
    def _onchange_invoice_ids(self):
        """Auto fill due date from first selected invoice"""
        if self.invoice_ids:
            # Sort invoices by due date to get the earliest one
            sorted_invoices = self.invoice_ids.sorted(lambda x: x.invoice_date_due or fields.Date.context_today(self))
            first_invoice = sorted_invoices[0]
            if first_invoice.invoice_date_due:
                self.due_date = first_invoice.invoice_date_due

    def action_confirm(self):
        """Confirm billing note"""
        for rec in self:
            if not rec.invoice_ids:
                raise UserError(_('Please select at least one document.'))
            rec.write({'state': 'confirm'})

    def action_done(self):
        """Mark billing note as done"""
        for rec in self:
            rec.write({'state': 'done'})

    def action_draft(self):
        """Reset billing note to draft"""
        for rec in self:
            rec.write({'state': 'draft'})

    def action_cancel(self):
        """Cancel billing note"""
        for rec in self:
            rec.write({'state': 'cancel'})

    @api.depends('invoice_ids')
    def _compute_sale_order_number(self):
        for rec in self:
            # ดึงเลขที่ Sale Order จาก invoice แรกที่มี sale_id
            sale_order = False
            for inv in rec.invoice_ids:
                if hasattr(inv, 'invoice_origin') and inv.invoice_origin:
                    sale_order = inv.invoice_origin
                    break
            rec.sale_order_number = sale_order or ''

    @api.depends('invoice_ids')
    def _compute_salesperson(self):
        for rec in self:
            # ดึง Salesperson จาก invoice แรก
            rec.salesperson_id = rec.invoice_ids and rec.invoice_ids[0].user_id.id or False

    @api.depends('invoice_ids')
    def _compute_payment_term(self):
        for rec in self:
            # ดึง Payment Term จาก invoice แรก
            rec.payment_term_id = rec.invoice_ids and rec.invoice_ids[0].invoice_payment_term_id.id or False

    @api.depends('invoice_ids')
    def _compute_invoice_due_date(self):
        for rec in self:
            # ดึง Due Date จาก invoice แรก
            rec.invoice_due_date = rec.invoice_ids and rec.invoice_ids[0].invoice_date_due or False