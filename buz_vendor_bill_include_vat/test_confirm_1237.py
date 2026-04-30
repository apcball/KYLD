import sys
from odoo.tools.misc import mute_logger

env = self.env
bill = env['account.move'].browse(1237)
if not bill.exists():
    print("Bill 1237 not found")
    sys.exit(0)

print(f"Bill 1237 state: {bill.state}")
print(f"Bill Debits: {sum(bill.line_ids.mapped('debit'))}, Credits: {sum(bill.line_ids.mapped('credit'))}")

try:
    bill.action_post()
    print("Confirm successful!")
except Exception as e:
    print(f"Error during confirm: {e}")

env.cr.rollback()
