import sys

env = self.env
Move = env['account.move']

# Find a draft vendor bill with VAT
bill = Move.browse(1237)
if not bill.exists() or bill.state != 'draft':
    print(f"Bill 1237 not found or not in draft state: {bill}")
    sys.exit(0)

print(f"Testing bill {bill.name} (ID: {bill.id})")

if bill.is_vat_included:
    print("Fixing inconsistent state: setting is_vat_included to False...")
    bill.is_vat_included = False

print("--- BEFORE INCLUDE VAT ---")
for line in bill.line_ids:
    print(f"Line {line.id} ({line.name}): display_type={line.display_type}, debit={line.debit}, credit={line.credit}, tax_ids={line.tax_ids.mapped('name')}, include_vat_cost={getattr(line, 'include_vat_cost', False)}")

print(f"Total Debits: {sum(bill.line_ids.mapped('debit'))}, Credits: {sum(bill.line_ids.mapped('credit'))}")

# Check lines to be processed
selected_lines = bill.invoice_line_ids.filtered(lambda line: line.include_vat_cost)
print(f"Selected lines to include VAT: {selected_lines.mapped('id')}")
if not selected_lines:
    print("Setting include_vat_cost on all invoice lines with taxes...")
    for line in bill.invoice_line_ids:
        if line.tax_ids:
            line.include_vat_cost = True

try:
    print("Including VAT...")
    bill.action_include_vat_in_price()
    print("Action successful.")
except Exception as e:
    import traceback
    print(f"Exception during action: {e}")
    traceback.print_exc()

print("--- AFTER INCLUDE VAT ---")
for line in bill.line_ids:
    print(f"Line {line.id} ({line.name}): display_type={line.display_type}, debit={line.debit}, credit={line.credit}, tax_ids={line.tax_ids.mapped('name')}, tax_line_id={line.tax_line_id.name}")

print(f"Total Debits: {sum(bill.line_ids.mapped('debit'))}, Credits: {sum(bill.line_ids.mapped('credit'))}")

# Check differences
diff = sum(bill.line_ids.mapped('debit')) - sum(bill.line_ids.mapped('credit'))
print(f"Difference: {diff}")

if diff != 0:
    print("Triggering sync dynamic lines manually to see if it fixes it...")
    # Odoo 17 dynamic lines are synced by default, but let's test a write to trigger compute
    bill.with_context(check_move_validity=False).write({'narration': 'Test trigger'})
    
    print("--- AFTER TRIGGER SYNC ---")
    for line in bill.line_ids:
        print(f"Line {line.id} ({line.name}): display_type={line.display_type}, debit={line.debit}, credit={line.credit}, tax_ids={line.tax_ids.mapped('name')}, tax_line_id={line.tax_line_id.name}")

    print(f"Total Debits: {sum(bill.line_ids.mapped('debit'))}, Credits: {sum(bill.line_ids.mapped('credit'))}")
    diff2 = sum(bill.line_ids.mapped('debit')) - sum(bill.line_ids.mapped('credit'))
    print(f"Difference after sync: {diff2}")


env.cr.rollback() # Don't commit
