# Service PO in Job Cost Sheets

Implemented a read-only **Service PO** tab for users with existing Purchase
access. Each confirmed service purchase order line appears separately, including
repeated products and descriptions. The tab opens the source PO and shows its
description, quantity, unit, price, untaxed subtotal, currency, and the amount
attributable to the sheet.

## Amounts and ownership

- Only `purchase` and `done` orders contribute; notes, sections, RFQs, cancelled
  orders, and non-service products are excluded.
- Allocation ownership takes precedence. Multiple allocations for the same
  sheet/PO line are combined once, using the allocated quantity's proportion of
  `price_subtotal`. Hidden allocations never cause a full-PO fallback.
- Without allocations, ownership follows the PO line's sheet, then its cost
  line's sheet, then the PO header. Project membership alone is insufficient.
- Source subtotals preserve existing discounts and negative amounts. Converted
  amounts use the sheet currency (company currency if unset), sheet company,
  and PO date. Quantities are in the PO line's unit, as defined by allocation.
- A zero-quantity PO line with an allocation remains visible with a warning;
  its amount is excluded and the total is explicitly labelled incomplete.
- Purchase and allocation record rules remain enforced; no elevated reads or
  new access grants are introduced. Totals cover records visible to the user.
- Computed values are not stored. Reload the form after changing a PO or its
  allocations. Reading the tab does not create or relink cost lines, or change
  BOQ/MR budgets and Actual costs.

## Implementation

- `models/service_po.py`: sheet membership, totals, context-dependent PO line
  amounts, and source-document action; imported by `models/__init__.py`.
- `views/job_cost_sheet_views.xml`: read-only table, summary, and warning.
- `tests/test_service_po.py`: 12 regression tests, imported by `tests/__init__.py`.

## Validation — 2026-09-11

Ran the complete module suite on a fresh local PostgreSQL instance:

```sh
docker compose -p kyld-service-po-test -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from odoo
```

Result: **43 tests, 0 failures, 0 errors; exit 0**, including all 12 new tests.
Coverage includes repeated descriptions across POs, negative values, taxes,
state changes and reload, ownership precedence, split allocations, zero ordered
quantity, historical currency conversion, hidden records, company boundaries,
view structure, and opening a PO. `git diff --check` also passed.

Odoo loaded and validated the XML view, and tests verified the resolved form
view and read-only controls. Visual browser interaction was not run; no browser
automation tooling is installed in this workspace/test image.

## Deployment boundary

No PROD data or files were changed. No data migration is needed: historical PO
lines appear when the module is upgraded to load the new code and view.
Deployment has not been performed.

Earlier read-only PROD inspection found that product 2438 in JCS/0025/2026 has
37 PO lines totalling 327,034 before tax, linked to one existing cost line showing
3,450. These records are an acceptance example for the new tab after deployment;
the new tab has not been run on PROD. Allocation, if present, determines the
sheet's share rather than the full PO total.

PROD's existing cost-sheet model and view differ from the local versions.
Review those differences when preparing a deployment; do not overwrite remote
changes as part of an unreviewed whole-module copy.
