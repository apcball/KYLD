import sys

env = self.env
Move = env['account.move']

# Create a test bill
partner = env['res.partner'].search([], limit=1)
tax = env['account.tax'].search([('type_tax_use', '=', 'purchase'), ('amount', '>', 0), ('price_include', '=', False)], limit=1)
if not tax:
    print("No purchase tax found.")
    sys.exit(0)
    
print(f"Using tax: {tax.name} (Amount: {tax.amount}, Group: {tax.tax_group_id.name})")
# Make sure the tax group has 'vat' in the name so the script processes it
tax.tax_group_id.name = 'VAT ' + tax.tax_group_id.name

bill = Move.create({
    'move_type': 'in_invoice',
    'partner_id': partner.id,
    'invoice_date': '2023-01-01',
    'invoice_line_ids': [
        (0, 0, {
            'name': 'Test product',
            'quantity': 1,
            'price_unit': 1000.0,
            'tax_ids': [(6, 0, [tax.id])],
            'include_vat_cost': True,
        })
    ]
})

print(f"Created Bill {bill.id}")
print("--- BEFORE INCLUDE VAT ---")
for line in bill.line_ids:
    print(f"Line {line.id}: type={line.display_type}, debit={line.debit}, credit={line.credit}, tax_ids={line.tax_ids.mapped('name')}, tax_line_id={line.tax_line_id.name}")

print(f"Total Debits: {sum(bill.line_ids.mapped('debit'))}, Credits: {sum(bill.line_ids.mapped('credit'))}")

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
    print(f"Line {line.id}: type={line.display_type}, debit={line.debit}, credit={line.credit}, tax_ids={line.tax_ids.mapped('name')}, tax_line_id={line.tax_line_id.name}")

print(f"Total Debits: {sum(bill.line_ids.mapped('debit'))}, Credits: {sum(bill.line_ids.mapped('credit'))}")

# Check differences
diff = sum(bill.line_ids.mapped('debit')) - sum(bill.line_ids.mapped('credit'))
print(f"Difference: {diff}")

# What happens if I confirm?
try:
    print("Confirming...")
    bill.action_post()
    print("Confirm successful.")
except Exception as e:
    import traceback
    print(f"Exception during confirm: {e}")

env.cr.rollback() # Don't commit
