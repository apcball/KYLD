import sys

env = self.env
bill = env['account.move'].browse(1237)

try:
    bill.action_post()
except Exception as e:
    pass

for line in bill.line_ids:
    if line.display_type == 'cogs' or line.debit == 22.57:
        print(f"Line {line.id}: product={line.product_id.name}, name={line.name}, debit={line.debit}, credit={line.credit}, price_unit={line.price_unit}, qty={line.quantity}, tax_ids={line.tax_ids.mapped('name')}")
        if line.purchase_line_id:
            print(f"  PO Line: price_unit={line.purchase_line_id.price_unit}, tax_ids={line.purchase_line_id.taxes_id.mapped('name')}")

env.cr.rollback()
