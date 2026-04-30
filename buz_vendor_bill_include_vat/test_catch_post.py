import sys

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
    # Print the lines in the current transaction state
    print("--- LINES AFTER FAILED POST ---")
    for line in bill.line_ids:
        print(f"Line {line.id}: type={line.display_type}, debit={line.debit}, credit={line.credit}, price_unit={line.price_unit}, qty={line.quantity}, tax_ids={line.tax_ids.mapped('name')}, tax_line_id={line.tax_line_id.name}")
    print(f"Total Debits: {sum(bill.line_ids.mapped('debit'))}, Credits: {sum(bill.line_ids.mapped('credit'))}")

env.cr.rollback()
