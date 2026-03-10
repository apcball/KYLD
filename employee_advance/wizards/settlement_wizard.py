from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class AdvanceSettlementWizard(models.TransientModel):
    _name = 'advance.settlement.wizard'
    _description = 'Advance Settlement Wizard'

    # Main fields
    box_id = fields.Many2one(
        'employee.advance.box',
        string='Advance Box',
        required=True,
        readonly=True,
        ondelete='cascade'
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        related='box_id.employee_id',
        readonly=True,
        compute_sudo=True
    )
    employee_name = fields.Char(
        string='Employee Name',
        related='box_id.employee_id.name',
        readonly=True,
        compute_sudo=True
    )
    box_name = fields.Char(
        string='Box Name',
        related='box_id.name',
        readonly=True,
        compute_sudo=True
    )

    # Computed current balance
    current_balance = fields.Monetary(
        string='Current Balance',
        compute='_compute_current_balance',
        currency_field='currency_id',
        compute_sudo=True,
        help='Current balance in the advance box: >0 = company owes employee; <0 = employee owes company'
    )

    # Parameters
    settlement_date = fields.Date(
        string='Settlement Date',
        default=fields.Date.context_today,
        required=True
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        domain="[('company_id', '=', company_id), ('type', 'in', ('bank', 'cash'))]",
        check_company=True
    )
    payment_account_id = fields.Many2one(
        'account.account',
        string='Payment Account (Cash/Bank)',
        domain="[('deprecated', '=', False), ('company_id', '=', company_id)]",
        check_company=True,
        help='Select which cash/bank account to use for the payment. Will default to journal default account if not specified.'
    )
    amount_mode = fields.Selection([
        ('full', 'Full Settlement'),
        ('partial', 'Partial Settlement')
    ], string='Amount Mode', default='full', required=True)
    amount_to_settle = fields.Monetary(
        string='Amount to Settle',
        currency_field='currency_id'
    )
    scenario = fields.Selection([
        ('pay_employee', 'Pay Employee (Dr Bank / Cr 141101) - Clear positive balance'),
        ('employee_refund', 'Employee Refund (Dr 141101 / Cr Bank) - Clear negative balance'),
        ('write_off', 'Write-off / Reclass'),
    ], string='Settlement Scenario', required=True, readonly=True,
        help="Auto-selected based on balance: Pay Employee when company owes employee (positive), Employee Refund when employee owes company (negative)")
    writeoff_policy = fields.Selection([
        ('none', 'No Write-off'),
        ('expense', 'Expense'),
        ('other_income', 'Other Income')
    ], string='Write-off Policy', default='none')
    writeoff_account_id = fields.Many2one(
        'account.account',
        string='Write-off Account',
        domain="[('deprecated', '=', False), ('company_id', '=', company_id)]",
        check_company=True
    )
    memo = fields.Char(
        string='Memo',
        default=lambda self: 'Advance Settlement for %s' % (self.env.context.get('default_employee_name', 'Employee'))
    )
    auto_reconcile = fields.Boolean(
        string='Auto Reconcile',
        default=True
    )
    create_activity = fields.Boolean(string='Create Activity')
    activity_user_id = fields.Many2one('res.users', string='Responsible User')
    activity_type_id = fields.Many2one('mail.activity.type', string='Activity Type')
    activity_note = fields.Text(string='Activity Note')

    # Computed fields
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='box_id.currency_id',
        readonly=True,
        compute_sudo=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        readonly=True,
    )

    target_amount = fields.Monetary(
        string='Target Amount',
        compute='_compute_target_amount',
        currency_field='currency_id'
    )
    direction = fields.Selection([
        ('positive', 'Company owes employee'),
        ('negative', 'Employee owes company')
    ], string='Direction', compute='_compute_direction')

    @api.model
    def default_get(self, fields):
        """Set default values based on the advance box"""
        res = super().default_get(fields)

        if self.env.context.get('default_box_id'):
            # Use sudo() to find the box and its company
            box = self.env['employee.advance.box'].sudo().browse(self.env.context['default_box_id'])
            if box.exists():
                company = box.company_id
                # Determine the default scenario based on balance
                if box.balance > 0:
                    default_scenario = 'pay_employee'
                elif box.balance < 0:
                    default_scenario = 'employee_refund'
                else:
                    default_scenario = 'write_off'

                # Try to set a default journal based on the advance box if available
                # Search normally to respect access rights, but filter by company
                default_journal = box.journal_id if box.journal_id and box.journal_id.type in ('bank', 'cash') and box.journal_id.company_id == company else self.env['account.journal']
                
                if not default_journal and default_scenario in ('pay_employee', 'employee_refund'):
                    default_journal = self.env['account.journal'].search([
                        ('company_id', '=', company.id),
                        ('type', 'in', ('bank', 'cash'))
                    ], limit=1, order="type desc, id asc")

                # Set payment account from journal's default account
                payment_account = default_journal.default_account_id if default_journal and default_journal.default_account_id else False

                res.update({
                    'box_id': box.id,
                    'company_id': company.id,
                    'current_balance': box.balance,
                    'memo': f'Advance Settlement for {box.employee_id.name}',
                    'scenario': default_scenario,
                    'journal_id': default_journal.id if default_journal else False,
                    'payment_account_id': payment_account.id if payment_account else False,
                })

        return res

    @api.depends('box_id')
    def _compute_current_balance(self):
        """Compute the current balance from the advance box"""
        for record in self:
            if record.box_id:
                record.current_balance = record.box_id.sudo().balance
            else:
                record.current_balance = 0.0

    @api.depends('amount_mode', 'amount_to_settle', 'current_balance')
    def _compute_target_amount(self):
        """Compute the target amount based on settlement mode"""
        for record in self:
            if record.amount_mode == 'partial' and record.amount_to_settle:
                record.target_amount = abs(record.amount_to_settle)
            else:
                record.target_amount = abs(record.current_balance) if record.current_balance else 0.0

    @api.depends('current_balance')
    def _compute_direction(self):
        """Compute the direction of the balance"""
        for record in self:
            if record.current_balance > 0:
                record.direction = 'positive'  # Company owes employee
            elif record.current_balance < 0:
                record.direction = 'negative'  # Employee owes company
            else:
                record.direction = False

    @api.onchange('box_id')
    def _onchange_box(self):
        """Update defaults based on selected box"""
        if self.box_id:
            box_sudo = self.box_id.sudo()
            self.company_id = box_sudo.company_id
            self.current_balance = box_sudo.balance
            self.memo = f'Advance Settlement for {box_sudo.employee_id.name}'
            # Set default scenario based on balance direction
            if box_sudo.balance > 0:
                self.scenario = 'pay_employee'
            elif box_sudo.balance < 0:
                self.scenario = 'employee_refund'
            else:
                self.scenario = 'write_off'

            # Auto-pick journal based on new box
            self._onchange_default_journal()

    @api.onchange('box_id', 'scenario')
    def _onchange_default_journal(self):
        """Auto-pick a sensible journal for scenarios that touch Bank/Cash."""
        for w in self:
            if w.scenario in ('pay_employee', 'employee_refund'):
                box_sudo = w.box_id.sudo()
                company = box_sudo.company_id
                journal = box_sudo.journal_id
                
                # Check accessibility and company
                if journal:
                    try:
                        journal.read(['name'])
                        if journal.company_id != company:
                            journal = self.env['account.journal']
                    except Exception:
                        journal = self.env['account.journal']

                if not journal and company:
                    journal = self.env['account.journal'].search([
                        ('type', 'in', ('bank','cash')),
                        ('company_id', '=', company.id)
                    ], limit=1, order="type desc, id asc")
                
                w.journal_id = journal or False
                if journal and journal.default_account_id:
                    w.payment_account_id = journal.default_account_id
            else:
                w.journal_id = False
                w.payment_account_id = False

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        """Update payment account when journal changes"""
        if self.journal_id and self.journal_id.default_account_id:
            self.payment_account_id = self.journal_id.default_account_id

    @api.constrains('scenario', 'journal_id', 'payment_account_id')
    def _check_journal_required(self):
        for w in self:
            if w.scenario in ('pay_employee', 'employee_refund'):
                if not w.journal_id:
                    raise ValidationError(_("Please select a Bank/Cash journal for this settlement scenario."))
                if not w.payment_account_id:
                    raise ValidationError(_("Please select a payment account (Cash/Bank) for this settlement scenario."))
                if w.journal_id.company_id != w.company_id:
                    raise ValidationError(_("Journal must belong to the same company as the advance box."))
            if w.scenario == 'write_off' and w.writeoff_policy != 'none' and not w.writeoff_account_id:
                raise ValidationError(_("Please select a write-off account when using write-off policy."))

    def _create_settlement_move(self):
        """Create the settlement journal entry"""
        self.ensure_one()
        box_sudo = self.box_id.sudo()
        company = box_sudo.company_id

        partner_id = box_sudo._get_employee_partner()
        if not partner_id:
            # Fallback
            employee = box_sudo.employee_id
            employee_partner = self.env['res.partner'].sudo().search([
                ('name', '=', employee.name),
                ('is_company', '=', False)
            ], limit=1)
            if not employee_partner:
                employee_partner = self.env['res.partner'].sudo().create({
                    'name': employee.name,
                    'is_company': False,
                    'employee': True,
                })
            partner_id = employee_partner.id

        journal_to_use = self.journal_id if self.scenario != 'write_off' else self._get_default_general_journal()

        move_vals = {
            'journal_id': journal_to_use.id,
            'move_type': 'entry',
            'date': self.settlement_date,
            'ref': self.memo or f'Advance Settlement for {box_sudo.employee_id.name}',
            'partner_id': partner_id,
            'company_id': company.id,
        }

        # Ensure journal has a sequence
        try:
            self.env['hr.expense.advance.journal.utils'].sudo().ensure_journal_sequence(journal_to_use)
        except Exception:
            pass

        lines = []
        if self.scenario == 'pay_employee':
            # Company pays employee
            lines.append((0, 0, {
                'account_id': self.payment_account_id.id,
                'partner_id': partner_id,
                'debit': self.target_amount,
                'credit': 0.0,
                'name': f'Settlement Payment to {box_sudo.employee_id.name}',
                'company_id': company.id,
            }))
            lines.append((0, 0, {
                'account_id': box_sudo.account_id.id,
                'partner_id': partner_id,
                'debit': 0.0,
                'credit': self.target_amount,
                'name': f'Settlement Payment to {box_sudo.employee_id.name}',
                'company_id': company.id,
            }))
        elif self.scenario == 'employee_refund':
            # Employee pays company
            lines.append((0, 0, {
                'account_id': box_sudo.account_id.id,
                'partner_id': partner_id,
                'debit': self.target_amount,
                'credit': 0.0,
                'name': f'Refund from {box_sudo.employee_id.name}',
                'company_id': company.id,
            }))
            lines.append((0, 0, {
                'account_id': self.payment_account_id.id,
                'partner_id': partner_id,
                'debit': 0.0,
                'credit': self.target_amount,
                'name': f'Refund from {box_sudo.employee_id.name}',
                'company_id': company.id,
            }))
        elif self.scenario == 'write_off':
            if self.writeoff_policy == 'expense':
                lines.append((0, 0, {
                    'account_id': self.writeoff_account_id.id,
                    'partner_id': partner_id,
                    'debit': self.target_amount,
                    'credit': 0.0,
                    'name': f'Write-off to Expense for {box_sudo.employee_id.name}',
                    'company_id': company.id,
                }))
                lines.append((0, 0, {
                    'account_id': box_sudo.account_id.id,
                    'partner_id': partner_id,
                    'debit': 0.0,
                    'credit': self.target_amount,
                    'name': f'Write-off to Expense for {box_sudo.employee_id.name}',
                    'company_id': company.id,
                }))
            elif self.writeoff_policy == 'other_income':
                lines.append((0, 0, {
                    'account_id': box_sudo.account_id.id,
                    'partner_id': partner_id,
                    'debit': 0.0,
                    'credit': self.target_amount,
                    'name': f'Write-off to Other Income for {box_sudo.employee_id.name}',
                    'company_id': company.id,
                }))
                lines.append((0, 0, {
                    'account_id': self.writeoff_account_id.id,
                    'partner_id': partner_id,
                    'debit': self.target_amount,
                    'credit': 0.0,
                    'name': f'Write-off to Other Income for {box_sudo.employee_id.name}',
                    'company_id': company.id,
                }))

        move_vals['line_ids'] = lines
        # CRITICAL: Create move with the correct company context and SUDO
        move = self.env['account.move'].with_company(company).sudo().create(move_vals)
        return move

    def _reconcile_141101_lines(self, move):
        """Reconcile lines"""
        if not self.auto_reconcile:
            return
        box_sudo = self.box_id.sudo()
        company = box_sudo.company_id
        partner_id = box_sudo._get_employee_partner()
        all_lines = self.env['account.move.line'].with_company(company).sudo().search([
            ('account_id', '=', box_sudo.account_id.id),
            ('partner_id', '=', partner_id),
            ('reconciled', '=', False),
            ('move_id.state', '=', 'posted'),
            ('company_id', '=', company.id),
        ])
        debit_lines = all_lines.filtered(lambda l: l.debit > 0)
        credit_lines = all_lines.filtered(lambda l: l.credit > 0)
        for debit_line in debit_lines:
            for credit_line in credit_lines:
                if debit_line.currency_id == credit_line.currency_id:
                    if debit_line.amount_residual != 0 and credit_line.amount_residual != 0:
                        try:
                            (debit_line + credit_line).reconcile()
                            break
                        except Exception:
                            continue

    def _get_default_general_journal(self):
        """Get default general journal"""
        company = self.box_id.company_id
        general_journal = self.env['account.journal'].sudo().search([
            ('type', '=', 'general'),
            ('company_id', '=', company.id)
        ], limit=1, order="id asc")
        if not general_journal:
            raise UserError(_("No general journal found for company %s.") % company.name)
        return general_journal

    def action_settle_advance(self):
        """Settle advance"""
        self.ensure_one()
        box_sudo = self.box_id.sudo()
        company = box_sudo.company_id
        try:
            move = self._create_settlement_move()
            move.action_post()
            if self.auto_reconcile:
                self._reconcile_141101_lines(move)
            box_sudo._trigger_balance_recompute()
            
            settlement_msg = _("Advance Settlement Completed: %s") % move.name
            box_sudo.message_post(body=settlement_msg)
            
            # Check if current user has access to the move's company in their UI context
            allowed_company_ids = self.env.context.get('allowed_company_ids', [self.env.company.id])
            if company.id in allowed_company_ids:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.move',
                    'res_id': move.id,
                    'view_mode': 'form',
                    'target': 'current',
                    'name': _('Settlement Journal Entry')
                }
            else:
                # Return notification if user can't see the move
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Settlement Created'),
                        'message': _('Journal Entry %s created in company %s. Please switch companies to view it.') % (move.name, company.name),
                        'type': 'success',
                        'sticky': False,
                        'next': {'type': 'ir.actions.client', 'tag': 'reload'},
                    }
                }
        except Exception as e:
            _logger.exception("Settlement failed")
            raise UserError(_("Settlement failed: %s") % str(e))
