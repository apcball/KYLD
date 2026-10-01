from odoo.tests import common, tagged
from odoo.exceptions import UserError, ValidationError
from odoo import fields

@tagged('post_install', '-at_install')
class TestAccountBankTransfer(common.TransactionCase):

    def setUp(self):
        super(TestAccountBankTransfer, self).setUp()
        
        self.company = self.env.company
        
        # Create Journals — use unique codes to avoid collision with MOG_DEV data
        import uuid
        self.bank_journal_1 = self.env['account.journal'].create({
            'name': 'Test Bank 1',
            'type': 'bank',
            'code': 'TBT' + uuid.uuid4().hex[:3].upper(),
            'currency_id': self.company.currency_id.id,
        })
        self.bank_journal_2 = self.env['account.journal'].create({
            'name': 'Test Bank 2',
            'type': 'bank',
            'code': 'TBT' + uuid.uuid4().hex[:3].upper(),
            'currency_id': self.company.currency_id.id,
        })

    def test_bank_transfer_flow(self):
        """ Test the bank transfer creation and confirmation """
        transfer = self.env['account.bank.transfer'].create({
            'journal_id': self.bank_journal_1.id,
            'destination_journal_id': self.bank_journal_2.id,
            'amount': 1000.0,
            'date': fields.Date.today(),
        })
        
        # Check initial state
        self.assertEqual(transfer.state, 'draft')
        
        # Confirm
        transfer.action_confirm()
        
        # Check state after confirm
        self.assertEqual(transfer.state, 'posted')
        self.assertTrue(transfer.payment_id, "Payment should be created")
        
        # Check Payment values
        payment = transfer.payment_id
        self.assertTrue(payment.is_internal_transfer)
        self.assertEqual(payment.journal_id, self.bank_journal_1)
        self.assertEqual(payment.destination_journal_id, self.bank_journal_2)
        self.assertEqual(payment.amount, 1000.0)
        self.assertEqual(payment.payment_type, 'outbound')
        
    def test_bank_transfer_constraints(self):
        """ Test constraints """
        # Same journal
        with self.assertRaises(UserError):
            transfer = self.env['account.bank.transfer'].create({
                'journal_id': self.bank_journal_1.id,
                'destination_journal_id': self.bank_journal_1.id,
                'amount': 1000.0,
            }).action_confirm()

        # Negative amount
        with self.assertRaises(UserError):
            transfer = self.env['account.bank.transfer'].create({
                'journal_id': self.bank_journal_1.id,
                'destination_journal_id': self.bank_journal_2.id,
                'amount': -100.0,
            }).action_confirm()

    def _enable_bank_charge(self):
        account = self.env['account.account'].create({
            'name': 'Test Bank Charge',
            'code': 'TBC' + self.bank_journal_1.code[-3:],
            'account_type': 'expense',
        })
        self.bank_journal_1.default_bank_charge_account_id = account
        return account

    def _new_transfer(self, fee):
        return self.env['account.bank.transfer'].create({
            'journal_id': self.bank_journal_1.id,
            'destination_journal_id': self.bank_journal_2.id,
            'amount': 1000.0,
            'bank_charge_amount': fee,
            'date': fields.Date.today(),
        })

    def test_bank_transfer_with_bank_charge(self):
        account = self._enable_bank_charge()
        transfer = self._new_transfer(30.0)
        transfer.action_confirm()
        move = transfer.payment_id.move_id
        charge_line = move.line_ids.filtered(lambda l: l.account_id == account)
        self.assertEqual(charge_line.debit, 30.0)
        self.assertEqual(sum(move.line_ids.mapped('debit')), sum(move.line_ids.mapped('credit')))
        bank_credit = sum(move.line_ids.filtered(
            lambda l: l.account_id == self.bank_journal_1.default_account_id).mapped('credit'))
        self.assertEqual(bank_credit, 1030.0)
        # destination side must not carry the fee again
        paired = transfer.payment_id.paired_internal_transfer_payment_id
        self.assertEqual(paired.bank_charge_amount, 0.0)
        self.assertEqual(paired.amount, 1000.0)
        self.assertFalse(paired.move_id.line_ids.filtered(lambda l: l.account_id == account))
        self.assertEqual(sum(paired.move_id.line_ids.filtered(
            lambda l: l.account_id == self.bank_journal_2.inbound_payment_method_line_ids[:1].payment_account_id
            or l.account_id == self.bank_journal_2.default_account_id).mapped('debit')), 1000.0)

    def test_bank_transfer_without_bank_charge(self):
        account = self._enable_bank_charge()
        transfer = self._new_transfer(0.0)
        transfer.action_confirm()
        self.assertFalse(transfer.payment_id.move_id.line_ids.filtered(lambda l: l.account_id == account))

    def test_bank_charge_requires_account(self):
        with self.assertRaises(UserError):
            self._new_transfer(30.0).action_confirm()

    def test_bank_charge_negative(self):
        with self.assertRaises(ValidationError):
            self._new_transfer(-1.0)

    def test_bank_charge_reset_to_draft(self):
        self._enable_bank_charge()
        transfer = self._new_transfer(30.0)
        transfer.action_confirm()
        transfer.action_draft()
        self.assertEqual(transfer.state, 'draft')
        self.assertIn(transfer.payment_id.state, ('draft', 'cancel'))
