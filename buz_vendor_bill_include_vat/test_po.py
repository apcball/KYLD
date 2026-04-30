import sys

env = self.env
PO = env['purchase.order'].search([('name', '=', 'APO2600827')])
if not PO:
    print("PO APO2600827 not found.")
    sys.exit(0)

print(f"PO {PO.name} (ID: {PO.id})")
print(f"PO Amount Total: {PO.amount_total}, Untaxed: {PO.amount_untaxed}, Tax: {PO.amount_tax}")

for line in PO.order_line:
    print(f"Line {line.id}: price_unit={line.price_unit}, subtotal={line.price_subtotal}, tax_ids={line.taxes_id.mapped('name')}")

bill = env['account.move'].search([('purchase_id', '=', PO.id), ('move_type', '=', 'in_invoice')], limit=1)
if bill:
    print(f"\nFound bill created from PO: {bill.name} (ID: {bill.id}, state: {bill.state})")
    for line in bill.invoice_line_ids:
        print(f"Bill Line {line.id}: price_unit={line.price_unit}, discount={line.discount}, tax_ids={line.tax_ids.mapped('name')}, include_vat_cost={getattr(line, 'include_vat_cost', False)}")
    print(f"Bill amount_total: {bill.amount_total}")

env.cr.rollback()
