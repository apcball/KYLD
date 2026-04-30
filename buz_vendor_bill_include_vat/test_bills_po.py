import sys

env = self.env
PO = env['purchase.order'].search([('name', '=', 'APO2600827')])
if not PO:
    print("PO APO2600827 not found.")
    sys.exit(0)

bills = env['account.move'].search([('purchase_id', '=', PO.id), ('move_type', '=', 'in_invoice')])
print(f"Found {len(bills)} bills for PO {PO.name}")
for bill in bills:
    print(f"\nBill {bill.name} (ID: {bill.id}, state: {bill.state})")
    print(f"Total Debits: {sum(bill.line_ids.mapped('debit'))}, Credits: {sum(bill.line_ids.mapped('credit'))}")
    
    print("--- LINES ---")
    for line in bill.line_ids:
        print(f"Line {line.id}: {line.display_type}, debit={line.debit}, credit={line.credit}, price_unit={line.price_unit}, qty={line.quantity}, tax_ids={line.tax_ids.mapped('name')}")

    try:
        bill.with_context(check_move_validity=True).action_post()
        print("Successfully confirmed!")
    except Exception as e:
        print(f"Error on confirm: {e}")

env.cr.rollback()
