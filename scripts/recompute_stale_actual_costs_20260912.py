# Data fix for PROD (job_costing_management): force-recompute the stored
# computed fields on job.cost.sheet that this audit found stale
# (docs/qa/prod_reliability_audit_20260912.md, Check 1 - 8 sheets with
# actual_total_cost/total_variance out of date vs a fresh recompute).
# _compute_actual_costs pulls live PO/bill/timesheet data via a raw SQL
# query, so it drifts from the stored value whenever new PO/bill/timesheet
# rows land after the field was last recomputed - Odoo does not auto-
# retrigger a stored field just because unrelated rows changed underneath
# its SQL query. The existing recompute_boq_totals_after_cancel_fix.py
# script only touches boq_totals/active_totals/sync_status, not
# actual_costs, so it did not fix this drift.
#
# Usage:
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/recompute_stale_actual_costs_20260912.py
#
# DRY_RUN = True: reports every sheet whose stored totals differ from a
# fresh recompute (all 5 dependent methods: _compute_boq_totals,
# _compute_active_totals, _compute_totals, _compute_actual_costs,
# _compute_variance). No writes, no commit.

DRY_RUN = False

JobCostSheet = env['job.cost.sheet'].sudo()

all_sheets = JobCostSheet.search([])
changed_sheets = []

for sheet in all_sheets:
    before = (sheet.boq_total_cost, sheet.active_total_cost, sheet.total_cost,
              sheet.actual_total_cost, sheet.total_variance)
    sheet._compute_boq_totals()
    sheet._compute_active_totals()
    sheet._compute_totals()
    sheet._compute_actual_costs()
    sheet._compute_variance()
    after = (sheet.boq_total_cost, sheet.active_total_cost, sheet.total_cost,
              sheet.actual_total_cost, sheet.total_variance)
    if before != after:
        changed_sheets.append((sheet, before, after))

print(f"{len(all_sheets)} sheets recomputed, {len(changed_sheets)} had stale stored totals:")
for sheet, before, after in changed_sheets:
    print(f"  Sheet {sheet.id} '{sheet.name}': boq {before[0]}->{after[0]}, active {before[1]}->{after[1]}, "
          f"total {before[2]}->{after[2]}, actual {before[3]}->{after[3]}, variance {before[4]}->{after[4]}")

if not DRY_RUN:
    env.cr.commit()
    print(f"\nCommitted. {len(changed_sheets)} sheet(s) updated.")
else:
    env.cr.rollback()
    print("\nDry run only (rolled back) - set DRY_RUN = False and re-run to apply.")
