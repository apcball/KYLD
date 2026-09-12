# Force-recompute the stored computed fields touched by the cancelled-BOQ
# fix (job_cost_sheet.py: _compute_boq_totals, _compute_active_totals,
# _compute_boq_sync_status). Deploying the code change alone does not
# retrigger these - Odoo only recomputes a stored computed field when one
# of its declared dependency fields actually changes value, and nothing
# wrote to material_cost_ids/boq_line_id.boq_id.state today.
#
# Usage:
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/recompute_boq_totals_after_cancel_fix.py
#
# DRY_RUN = True: reports which sheets have a cancelled BOQ and what their
# boq_total_cost/active_total_cost would become. No writes, no commit.

DRY_RUN = True

JobCostSheet = env['job.cost.sheet'].sudo()

all_sheets = JobCostSheet.search([])
affected = all_sheets.filtered(lambda s: any(b.state == 'cancelled' for b in s.boq_ids))
print(f"{len(all_sheets)} sheets scanned, {len(affected)} have at least one cancelled BOQ")

for sheet in affected:
    before = (sheet.boq_total_cost, sheet.active_total_cost, sheet.has_unsynced_boq)
    sheet._compute_boq_totals()
    sheet._compute_active_totals()
    sheet._compute_boq_sync_status()
    after = (sheet.boq_total_cost, sheet.active_total_cost, sheet.has_unsynced_boq)
    changed = before != after
    print(f"Sheet {sheet.id} '{sheet.name}': boq_total {before[0]} -> {after[0]}, "
          f"active_total {before[1]} -> {after[1]}, has_unsynced_boq {before[2]} -> {after[2]}"
          f"{' [CHANGED]' if changed else ''}")

# Recompute every sheet, not just the ones with a cancelled BOQ - the
# @api.depends chain also now includes boq_line_id.boq_id.state, so every
# sheet's dependency graph technically changed even if the value doesn't.
for sheet in all_sheets - affected:
    sheet._compute_boq_totals()
    sheet._compute_active_totals()
    sheet._compute_boq_sync_status()

if not DRY_RUN:
    env.cr.commit()
    print(f"\nCommitted. Recomputed {len(all_sheets)} sheet(s) total.")
else:
    env.cr.rollback()
    print("\nDry run only (rolled back) - set DRY_RUN = False and re-run to apply.")
