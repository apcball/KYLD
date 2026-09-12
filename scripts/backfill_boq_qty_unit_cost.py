# Data fix for PROD (job_costing_management): job.cost.line rows that are
# linked to a boq.line (boq_line_id set) but never got boq_qty/boq_unit_cost
# stamped - both sit at 0, so boq_total_cost (= boq_qty * boq_unit_cost,
# job_cost_sheet.py:741) computes to 0 for them even though planned_qty /
# unit_cost / total_cost (the real budget numbers) are correct on the same
# row. This drags down job.cost.sheet.boq_total_cost, understating the "BOQ
# Total Cost" tile without affecting the actual budget total.
#
# Root cause: action_create_job_cost_lines (boq.py:353-364) only stamps
# boq_qty/boq_unit_cost on the CREATE branch. When _get_cost_line
# (boq.py:705-716) finds an already-linked line instead, nothing is written -
# there is no update path. Rows affected here predate that matching and were
# never backfilled.
#
# Confirmed instance: sheet 10 (JCS/0010/2025), BOQ00011 - 34 lines,
# 894,332.44 short on boq_total_cost. 2026-09-12.
#
# Usage (on the PROD host, after module is up to date):
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/backfill_boq_qty_unit_cost.py
#
# First run leaves DRY_RUN = True: only prints what WOULD change, no writes,
# no commit. Review the printed list, then edit this file to set
# DRY_RUN = False and re-run to actually apply + commit.

DRY_RUN = False

JobCostLine = env['job.cost.line'].sudo()

candidates = JobCostLine.search([
    ('boq_line_id', '!=', False),
    ('boq_qty', '=', 0),
    ('boq_unit_cost', '=', 0),
])
print(f"Scanning {len(candidates)} job.cost.line rows with boq_line_id set but boq_qty=boq_unit_cost=0...")

fixed = []
skipped = []

for line in candidates:
    boq_line = line.boq_line_id
    qty = boq_line.quantity
    unit_cost = boq_line.unit_cost

    if not qty and not unit_cost:
        skipped.append({
            'line': line.id, 'sheet': line.cost_sheet_id.name,
            'boq_line': boq_line.id,
            'reason': 'boq_line itself has qty=0 and unit_cost=0, nothing to backfill',
        })
        continue

    fixed.append({
        'line': line.id, 'sheet': line.cost_sheet_id.name, 'boq_line': boq_line.id,
        'boq_qty': qty, 'boq_unit_cost': unit_cost, 'boq_total_cost': qty * unit_cost,
    })

    if not DRY_RUN:
        line.write({'boq_qty': qty, 'boq_unit_cost': unit_cost})

print(f"\n=== {'DRY RUN - no changes made' if DRY_RUN else 'APPLIED'} ===")
print(f"To fix: {len(fixed)}")
for row in fixed:
    print(f"  cost_line {row['line']} (sheet '{row['sheet']}', boq_line {row['boq_line']}): "
          f"boq_qty 0 -> {row['boq_qty']}, boq_unit_cost 0 -> {row['boq_unit_cost']} "
          f"(boq_total_cost -> {row['boq_total_cost']})")

print(f"\nSkipped (needs manual review): {len(skipped)}")
for row in skipped:
    print(f"  cost_line {row['line']} (sheet '{row['sheet']}', boq_line {row['boq_line']}): {row['reason']}")

if not DRY_RUN:
    sheet_ids = {JobCostLine.browse(row['line']).cost_sheet_id.id for row in fixed}
    env['job.cost.sheet'].sudo().browse(list(sheet_ids))._compute_boq_totals()
    env.cr.commit()
    print(f"\nCommitted. Recomputed BOQ totals for {len(sheet_ids)} job cost sheet(s).")
else:
    print("\nDry run only - set DRY_RUN = False at top of script and re-run to apply.")
