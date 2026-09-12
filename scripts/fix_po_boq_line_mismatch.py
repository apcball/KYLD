# Data fix for PROD (job_costing_management): PO lines that were auto-linked
# to the WRONG job.cost.line because the fallback matcher (pre-fix) only
# scoped by product_id + name, not boq_line_id. Two BOQ lines that happen to
# share product AND description text could steal each other's actual cost.
#
# Confirmed instance: sheet 10, product 1477 - PO line 3497 (from BOQ line
# 3906) landed on job.cost.line 259 (boq_line_id=1385) instead of 1420
# (boq_line_id=3906).
#
# Run AFTER deploying the code fix (job_costing_management/models/purchase_order.py,
# commit ae5e783), so newly created cost lines from now on get boq_line_id
# stamped and the fallback match won't steal wrong lines again.
#
# Usage (on the PROD host, after `docker exec -i odoo` has module updated):
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/fix_po_boq_line_mismatch.py
#
# First run leaves DRY_RUN = True: it only prints what WOULD change, no writes,
# no commit. Review the printed list, then edit this file to set
# DRY_RUN = False and re-run to actually apply + commit.

DRY_RUN = True

JobCostLine = env['job.cost.line'].sudo()
POLine = env['purchase.order.line'].sudo()

fixed = []
skipped = []

po_lines = POLine.search([('material_requisition_line_id', '!=', False)])
print(f"Scanning {len(po_lines)} PO lines with a material requisition link...")

for pol in po_lines:
    req_line = pol.material_requisition_line_id
    boq_line = req_line.boq_line_id
    if not boq_line:
        continue

    current = pol.job_cost_line_id
    if not current:
        continue

    # Already correctly linked (or linked to a manually-created cost line
    # with no boq_line_id at all - ambiguous, leave alone).
    if not current.boq_line_id or current.boq_line_id.id == boq_line.id:
        continue

    # Mismatch signature: current cost line belongs to a DIFFERENT BOQ line.
    correct = JobCostLine.search([
        ('cost_sheet_id', '=', current.cost_sheet_id.id),
        ('boq_line_id', '=', boq_line.id),
    ], limit=1)

    if not correct:
        skipped.append({
            'po_line': pol.id, 'po': pol.order_id.name,
            'wrong_cost_line': current.id, 'expected_boq_line': boq_line.id,
            'reason': 'no job.cost.line exists yet for the expected BOQ line',
        })
        continue

    if correct.id == current.id:
        continue

    fixed.append({
        'po_line': pol.id, 'po': pol.order_id.name,
        'from_cost_line': current.id, 'to_cost_line': correct.id,
        'boq_line': boq_line.id, 'cost_sheet': current.cost_sheet_id.name,
    })

    if not DRY_RUN:
        old_line = current
        pol.job_cost_line_id = correct.id
        old_line.update_actual_costs_from_purchases()
        correct.update_actual_costs_from_purchases()

print(f"\n=== {'DRY RUN - no changes made' if DRY_RUN else 'APPLIED'} ===")
print(f"To fix: {len(fixed)}")
for row in fixed:
    print(f"  PO {row['po']} line {row['po_line']}: cost_line {row['from_cost_line']} -> {row['to_cost_line']} "
          f"(boq_line {row['boq_line']}, sheet '{row['cost_sheet']}')")

print(f"\nSkipped (needs manual review): {len(skipped)}")
for row in skipped:
    print(f"  PO {row['po']} line {row['po_line']}: currently on cost_line {row['wrong_cost_line']}, "
          f"expected boq_line {row['expected_boq_line']} has no cost line yet - {row['reason']}")

if not DRY_RUN:
    # Recompute sheet-level totals for every affected sheet.
    sheet_ids = set()
    for row in fixed:
        sheet_ids.add(env['job.cost.line'].sudo().browse(row['to_cost_line']).cost_sheet_id.id)
    env['job.cost.sheet'].sudo().browse(list(sheet_ids))._compute_actual_costs()
    env.cr.commit()
    print(f"\nCommitted. Recomputed totals for {len(sheet_ids)} job cost sheet(s).")
else:
    print("\nDry run only - set DRY_RUN = False at top of script and re-run to apply.")
