# Marketplace Settlement

This module extends Odoo's accounting capabilities to handle the complexities of e-commerce marketplace settlements (Shopee, Lazada, TikTok, NocNoc, etc.). It streamlines the process of reconciling customer invoices, managing marketplace fees (vendor bills), conducting AR/AP netting, and allocating fees to individual sales for profitability reporting.

## Key Features

1. **Trade Channel Profiles (`marketplace.settlement.profile`)**
   - Configure default accounts, journals, and partners for different marketplace channels (e.g., Shopee, Lazada, SPX).
   - Define default expense accounts for different fee types (Commission, Service Fee, Advertising, Logistics).
   - Set up document matching patterns for automatic profile detection (e.g., `TR` for Shopee Tax Invoices, `RC` for SPX Receipts).

2. **Marketplace Vendor Bills (`marketplace.vendor.bill`)**
   - Dedicated model to manage marketplace fee invoices and receipts.
   - Automatically calculate VAT and Withholding Tax (WHT) on fees based on profile defaults or manual configurations.
   - Allows users to link bills to settlements for subsequent netting.

3. **Settlement Management (`marketplace.settlement`)**
   - Groups posted customer invoices (`out_invoice`) by trade channel to create a consolidated settlement.
   - Generates the primary journal entry: `Dr. AR-Marketplace / Cr. AR-Customer`.
   - Reconciles the customer invoices automatically.

4. **AR/AP Netting (`marketplace.netting.wizard`)**
   - Instead of direct deductions on the settlement move, this module uses a formalized AR/AP netting process.
   - Users select outstanding Vendor Bills (AP) to net against the Marketplace Settlement (AR).
   - Computes the final Net Payout Amount expected in the bank statement.

5. **Fee Allocation (`marketplace.fee.allocation`)**
   - Allocates the aggregated fees, VAT, and WHT from Vendor Bills down to the individual customer invoice level.
   - Supports proportional allocation (based on pre-tax invoice amounts) or exact value allocation (from CSV imports).
   - Enables accurate per-order profitability analysis.

6. **Thai Localization Support**
   - Integrates with Thai Withholding Tax (WHT) modules.
   - Configures WHT rates and tracks WHT on marketplace fees correctly through the Vendor Bill flow.

## Business Workflow

1. **Process Sales**: Generate and post regular customer invoices in Odoo for marketplace orders.
2. **Record Fees**: Receive tax invoices/receipts from the marketplace (e.g., Shopee TR document) and enter them as **Marketplace Vendor Bills**.
3. **Create Settlement**: Use the Settlement Wizard to group customer invoices and create the Settlement (AR-Marketplace).
4. **Net-off AR/AP**: Use the Netting Wizard on the Settlement to offset the Vendor Bills against the Settlement AR.
5. **Allocate Fees**: Generate proportional fee allocations to review the true net payout of each customer invoice.
6. **Reconcile Payment**: Reconcile the remaining net AR balance with the actual incoming bank payout.

## Technical Notes
- **Dependencies**: `account`, `sale`
- **License**: LGPL-3
