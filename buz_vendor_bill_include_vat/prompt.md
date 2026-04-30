# Prompt: Implement Odoo 17 Module `buz_vendor_bill_include_vat`

You are a senior Odoo 17 developer.

Create a production-grade custom module named:

`buz_vendor_bill_include_vat`

---

# Business Objective

For some companies (especially real estate / property development), certain vendor bill VAT cannot be claimed as input tax.

Instead of separating VAT into tax lines, users need to convert VAT into product/service cost.

Example:

Before:

| Product | Amount | VAT | Total |
|--------|--------|-----|------|
| Material A | 100 | 7 | 107 |

After clicking button:

| Product | Amount |
|--------|--------|
| Material A | 107 |

Tax lines removed.

Accounting result:

Before:
- Expense = 100
- Input VAT = 7
- AP = 107

After:
- Expense = 107
- AP = 107

---

# Core Requirement

Users create Vendor Bill normally from Purchase Order first.

Then user clicks button:

## `Include VAT in Price`

System will:

1. Detect selected vendor bill (`account.move`)
2. Only allow:
   - move_type = `in_invoice`
   - move_type = `in_refund`
   - state = draft
3. Process invoice lines
4. Merge VAT into `price_unit`
5. Remove VAT taxes from selected lines
6. Recompute accounting move correctly
7. Ensure debit = credit balanced
8. Prevent duplicate processing

---

# Important Design Rule

## DO NOT manually delete tax move lines.

Use Odoo recompute engine properly.

Use:

- invoice_line_ids update
- tax_ids clear on invoice lines
- then trigger recomputation using Odoo 17 standard methods

Examples:

```python
move._recompute_dynamic_lines(recompute_all_taxes=True)

Functional Requirements
1. Add Fields
account.move
is_vat_included = fields.Boolean(copy=False)
account.move.line
include_vat_cost = fields.Boolean(
    string="Include VAT",
    help="If checked, VAT of this line will be moved into cost."
)
original_price_unit = fields.Float(copy=False)
vat_included_amount = fields.Monetary(copy=False)
2. UI Requirements
Vendor Bill Form

Add button visible only when:

draft
vendor bill / vendor credit note
not processed yet

Button label:

Include VAT in Price
Invoice Line Tree

Add checkbox column:

Include VAT

Users can choose only some lines.

3. Logic Rules

For each selected line:

Ignore if:
no tax_ids
display_type line
section/note
quantity = 0
Calculate:

Use standard tax engine:

taxes = line.tax_ids.compute_all(
    price_unit_after_discount,
    currency=move.currency_id,
    quantity=line.quantity,
    product=line.product_id,
    partner=move.partner_id,
)

Find VAT taxes only.

Only merge taxes where:

amount > 0
tax group indicates VAT / purchase tax
not price_include

Compute:

new subtotal = subtotal + vat
new price_unit = recalculated based on qty and discount

Then:

line.price_unit = new_price
line.tax_ids = clear VAT taxes only

Non-VAT taxes remain if applicable.

4. Mixed Tax Support

If line has:

VAT 7%
withholding tax
other taxes

Only remove VAT taxes.

Keep other taxes.

5. Recompute Move

After all lines processed:

Use one batch write if possible.

Then call recompute methods so:

tax lines regenerate
payable line recalculates
journal entry balanced

Must work in Odoo 17.

6. Validation

Raise UserError if:

already processed
no lines selected
posted move
wrong move type
7. Chatter Log

Post message:

VAT included into selected lines successfully.

Include summary:

lines count
total VAT moved
8. Optional Reverse Button

Implement second button:

Restore VAT

Use stored original values:

original_price_unit
original tax_ids if stored

Restore bill to original state.

(If too large, make clean scaffold ready)

Technical Standards

Use Odoo 17 best practices.

Folder structure:

buz_vendor_bill_include_vat/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── account_move.py
│   └── account_move_line.py
├── views/
│   └── account_move_views.xml
├── security/
│   └── ir.model.access.csv
Code Quality Rules
clean readable code
comments for important logic
no hacky SQL
no direct delete tax lines
production safe
support multi-currency
support discount lines
support refund bill
Output Needed

Generate complete Odoo 17 module source code.

Include:

manifest
python models
xml views
security
tested business logic
Final Goal

When user clicks button on draft Vendor Bill:

Before:

Expense 100
VAT 7
AP 107

After:

Expense 107
AP 107

And journal entry remains balanced with no errors.