# Data fix for PROD (job_costing_management): JCS/0059/2026 has 13 labour
# job.cost.line rows with boq_line_id = NULL that duplicate a BOQ-linked
# line for the same product (same product_id, matching unit_cost). These
# orphan lines inflate active_total_cost (Active Planned) without counting
# toward boq_total_cost (Budget), which is why the sheet showed:
#   Budget (BOQ)     664,369.64
#   Active Planned  1,134,704.81   (664,369.64 + 470,335.17 from 83 orphan
#                                   lines across material+labour)
#
# This script targets only the 11 labour-line duplicates confirmed to have
# an unambiguous BOQ-linked sibling with an identical unit_cost (excludes
# product 3076/3077 retention +/- pair, and product 1483 which has 3
# candidate BOQ siblings - ambiguous, left for manual review).
#
# Several of these orphan lines ALSO have a real purchase.order.line
# attached (source_po_line_id / purchase_order_line.job_cost_line_id) -
# i.e. actual PO cost landed on the WRONG (non-BOQ) cost line. This is the
# same fallback-matcher bug class as scripts/fix_po_boq_line_mismatch.py
# (product+name matching without boq_line_id scoping), just surfacing here
# as a labour-side instance on sheet 59.
#
# Fix per duplicate pair:
#   1. Relink any purchase.order.line.job_cost_line_id from the orphan to
#      the correct BOQ-linked cost line.
#   2. Recompute actual costs on both (old line's actual should drop to 0,
#      correct line's actual should pick up what moved).
#   3. Unlink the orphan job.cost.line (only if, after step 1, it has no
#      other actual-cost sources left: timesheet_ids, invoice_line_ids).
#
# Usage (on PROD host):
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/fix_jcs0059_duplicate_labour_lines.py
#
# First run leaves DRY_RUN = True: prints the plan only, no writes, no
# commit. Review the printed list, then edit this file to set
# DRY_RUN = False and re-run to actually apply + commit.

DRY_RUN = False

JobCostLine = env['job.cost.line'].sudo()
POLine = env['purchase.order.line'].sudo()
Sheet = env['job.cost.sheet'].sudo()

sheet = Sheet.search([('name', '=', 'JCS/0059/2026')], limit=1)
if not sheet:
    raise SystemExit("JCS/0059/2026 not found - check the sheet still exists / name unchanged")

print(f"Target sheet: {sheet.name} (id {sheet.id}), state={sheet.state}")

# Products excluded from auto-fix: retention +/- pair (not duplicates), and
# any product with more than one BOQ-linked candidate (ambiguous).
EXCLUDE_PRODUCTS = {3076, 3077}

orphan_lines = JobCostLine.search([
    ('cost_sheet_id', '=', sheet.id),
    ('cost_type', '=', 'labour'),
    ('boq_line_id', '=', False),
])

planned = []
skipped = []

for orphan in orphan_lines:
    pid = orphan.product_id.id
    if pid in EXCLUDE_PRODUCTS:
        continue

    candidates = JobCostLine.search([
        ('cost_sheet_id', '=', sheet.id),
        ('cost_type', '=', 'labour'),
        ('boq_line_id', '!=', False),
        ('product_id', '=', pid),
    ])

    if not candidates:
        skipped.append((orphan, 'no BOQ-linked sibling for this product'))
        continue

    exact = candidates.filtered(lambda l: abs(l.unit_cost - orphan.unit_cost) < 0.01)

    if len(exact) != 1:
        skipped.append((orphan, f'{len(candidates)} BOQ-linked candidate(s), {len(exact)} exact unit_cost match - ambiguous'))
        continue

    correct = exact[0]
    po_lines = POLine.search([('job_cost_line_id', '=', orphan.id)])

    planned.append({
        'orphan': orphan,
        'correct': correct,
        'po_lines': po_lines,
    })

print(f"\n=== {'DRY RUN - no changes made' if DRY_RUN else 'APPLIED'} ===")
print(f"\nPlanned fixes: {len(planned)}")
for row in planned:
    o, c = row['orphan'], row['correct']
    print(f"  orphan cost_line {o.id} (product {o.product_id.id}, '{o.name[:40]}', "
          f"unit_cost {o.unit_cost}, actual_cost {o.actual_cost}) "
          f"-> correct cost_line {c.id} (boq_line {c.boq_line_id.id})")
    for pol in row['po_lines']:
        print(f"      relink PO {pol.order_id.name} line {pol.id} (price {pol.price_unit}) "
              f"from cost_line {o.id} to {c.id}")
    if not row['po_lines']:
        print(f"      no PO lines attached - orphan will be unlinked directly")

print(f"\nSkipped (needs manual review): {len(skipped)}")
for orphan, reason in skipped:
    print(f"  cost_line {orphan.id} (product {orphan.product_id.id}, '{orphan.name[:40]}') - {reason}")

if not DRY_RUN:
    for row in planned:
        orphan, correct, po_lines = row['orphan'], row['correct'], row['po_lines']
        for pol in po_lines:
            pol.job_cost_line_id = correct.id
        if po_lines:
            orphan.update_actual_costs_from_purchases()
            correct.update_actual_costs_from_purchases()

        orphan.invalidate_recordset()
        if not orphan.timesheet_ids and not orphan.invoice_line_ids and not orphan.purchase_order_line_ids:
            orphan.unlink()
        else:
            print(f"  WARNING: cost_line {orphan.id} still has other actual-cost sources after relink - left in place, review manually")

    sheet._compute_active_totals()
    sheet._compute_boq_totals()
    env.cr.commit()
    print(f"\nCommitted. Sheet '{sheet.name}': "
          f"Budget {sheet.boq_total_cost}, Active Planned {sheet.active_total_cost}")
else:
    print("\nDry run only - set DRY_RUN = False at top of script and re-run to apply.")
