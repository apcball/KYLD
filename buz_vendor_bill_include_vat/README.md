# buz_vendor_bill_include_vat

## Overview

The **Include VAT in Price** module adds a button to vendor bills that moves the VAT amount from tax lines into the product `price_unit`. After execution, the bill lines become tax‑free and the VAT is already reflected in the unit price, making the bill easier to read and simplifying downstream reporting.

## Key Features

- Adds a boolean field `is_vat_included` to `account.move` to track whether VAT has been merged into the price.
- Adds a checkbox column in the invoice line tree view to select which lines to process.
- Provides the `action_include_vat_into_price` wizard that:
  1. Validates the bill is a draft vendor bill (`in_invoice` or `in_refund`).
  2. Iterates over each selected invoice line, computes the tax‑inclusive total, and back‑calculates a new `price_unit`.
  3. Rounds the new price using **Product Price** decimal precision (typically 4 dp) to avoid currency rounding mismatches.
  4. Clears the `tax_ids` on the line and writes all changes in a single `move.write()` call, ensuring Odoo 17’s `_sync_dynamic_lines` recomputes tax and payment‑term lines correctly.
  5. Stores original tax information for restoration.
- Adds a **Restore VAT** button to revert changes.
- Adds an **Include VAT All** button to process every taxable invoice line in one click.
- Posts a system message on the bill confirming the operation.

## Deep‑Level Analysis

### 1. VAT Calculation Accuracy

- **Full Line Context**: The method uses `tax_ids.compute_all` with the discounted `price_unit`, the line quantity, product, partner, and refund flag. This mirrors Odoo’s native tax computation, guaranteeing that the same tax rules (including fiscal positions, tax groups, and rounding methods) are applied.
- **Discount Handling**: When a line has a discount, the code first calculates the discounted unit price (`line_discount_price_unit`) and then recomputes taxes on that amount. The back‑calculation reverses the discount to obtain a new `price_unit` that, when multiplied by the original quantity and discount factor, reproduces the tax‑inclusive total.
- **Rounding Strategy**: The new `price_unit` is rounded to the **Product Price** precision (`price_dp`). This is crucial because rounding to currency precision (2 dp) could cause `price_unit × qty` to differ from the tax‑inclusive total, leading to an unbalanced journal entry. By using product precision (often 4 dp), the module keeps the line total within the currency’s rounding tolerance while preserving accounting integrity.

### 2. Tax Handling Logic

- **Selective Tax Inclusion**: Only taxes that are **not** already price‑included (`price_include=False`) and have a positive amount are processed. This prevents double‑inclusion of taxes that are already embedded in the price or have a zero rate.
- **VAT Detection**: Improved detection using tax group names to identify VAT taxes more reliably.
- **Tax Clearing**: After the new unit price is set, `tax_ids` are cleared with `Command.clear()`. This removes tax lines from the move, but the tax amount remains embedded in the line total, satisfying the requirement of “VAT included in price”.
- **Batch Write**: All line updates are accumulated in `line_updates` and written in a single `move.write()` call. This triggers Odoo 17’s `_sync_dynamic_lines` once, ensuring that dynamic tax and payment‑term lines are regenerated correctly and that the move stays balanced.

### 3. Edge Cases & Safeguards

| Edge Case | Handling |
|-----------|----------|
| **Non‑draft bills** | Raises `UserError` – only draft bills can be modified.
| **Non‑vendor moves** | Raises `UserError` – the action is limited to `in_invoice` and `in_refund` types.
| **Already processed bills** | Raises `UserError` if `is_vat_included` is `True`.
| **Lines without taxes** | Skipped – no changes are made, preserving original pricing.
| **Zero quantity** | Falls back to the original `price_unit` to avoid division by zero.
| **Zero discount** | Simplified back‑calculation without discount factor.
| **Multiple taxes on a line** | All applicable non‑inclusive taxes are aggregated before back‑calculation, ensuring the total tax amount is fully incorporated.
| **Mixed taxes** | Only VAT taxes are removed, other taxes (e.g., withholding) are preserved.

### 4. Performance Considerations

- The method loops over each line of the move, but the operations are lightweight (tax computation and a few arithmetic steps). For typical vendor bills (≤ 50 lines) the execution time is negligible.
- The single `write` operation minimizes database round‑trips and ensures atomicity.

## Usage Guide

1. Open a **Vendor Bill** (`Accounting → Vendor Bills`).
2. Select lines using the checkbox column in the invoice lines tree view.
3. Click the **Include VAT in Price** button (visible only on draft bills).
4. The system will process each selected line, update the unit price, clear taxes, and set the `VAT Included` flag.
5. A confirmation message appears in the chatter.
6. To revert changes, click the **Restore VAT** button.

## Limitations & Future Enhancements

- The current implementation does not support **price‑included taxes** (e.g., taxes already baked into the product price). Extending the logic to detect and handle such cases could be a future improvement.
- Multi‑currency scenarios rely on the currency conversion already performed by `compute_all`. Additional validation may be required for bills where the company currency differs from the vendor’s currency.

## Changelog

- **1.0.0** – Initial release with VAT inclusion button and robust rounding.
- **1.0.1** – Minor bug fixes and documentation updates.
- **1.0.2** – Major improvements including:
  - Improved VAT detection using tax group names
  - Better discount handling
  - Batch write optimization
  - Restore functionality
  - Proper tax storage for restoration
  - Correct Odoo 17 recomputation methods

## License

AGPL‑3
