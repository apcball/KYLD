from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class AccountPayment(models.Model):
    _inherit = 'account.payment'
    
    buz_payment_voucher_id = fields.Many2one(
        'account.payment.voucher',
        string='Payment Voucher',
        ondelete='set null',
        index=True,
        copy=False,
    )

    def copy(self, default=None):
        # The paired payment of an internal transfer is built with copy(); the bank
        # charge (sr_extra_bank_charges) belongs to the source payment only.
        # Odoo re-syncs payment.amount from the posted liquidity line, which already
        # includes the charge, so the paired payment must receive amount - charge.
        if default and default.get('paired_internal_transfer_payment_id') and self.bank_charge_amount:
            default = dict(
                default,
                bank_charge_amount=0.0,
                amount=self.amount - self._get_bank_charge_in_payment_currency(),
            )
        return super().copy(default)

