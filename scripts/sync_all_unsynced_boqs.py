# Bulk version of sync_missing_boq_cost_lines.py - instead of a hardcoded
# list of boq_line ids, scans EVERY job.cost.sheet for has_unsynced_boq
# (job_cost_sheet.py _compute_boq_sync_status: BOQ linked but its lines were
# never materialized into job.cost.line via "Create Job Cost Lines") and
# syncs every BOQ behind it. Fixes the "BOQ Costs (Baseline Budget) = 0.00"
# banner across the whole DB instead of one sheet/BOQ at a time.
#
# Usage:
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/sync_all_unsynced_boqs.py
#
# DRY_RUN = True: only reports affected sheets/BOQs and how many cost lines
# each BOQ is missing. No writes, no commit.
#
# DRY_RUN = False: applies and commits ONE JOB COST SHEET AT A TIME (not one
# big transaction) so a failure partway through a 59-sheet run doesn't lose
# already-applied sheets, and so progress is visible sheet by sheet.

DRY_RUN = True

JobCostSheet = env['job.cost.sheet'].sudo()

all_sheets = JobCostSheet.search([])
affected = all_sheets.filtered('has_unsynced_boq')
print(f"{len(all_sheets)} job cost sheets scanned, {len(affected)} have unsynced BOQ(s)")

boqs_done = set()
total_created = 0
sheets_failed = []

for sheet in affected:
    print(f"\nSheet {sheet.id} '{sheet.name}' (project: {sheet.project_id.display_name})")
    sheet_created = 0
    try:
        for boq in sheet.boq_ids:
            if boq.id in boqs_done:
                continue
            boqs_done.add(boq.id)
            lines = boq.line_ids.filtered('product_id')
            if not lines:
                print(f"  BOQ {boq.id} ({boq.display_name}): no product lines, skipping")
                continue
            if DRY_RUN:
                missing = sum(1 for line in lines if not line._get_cost_line(boq.job_cost_sheet_id))
                print(f"  BOQ {boq.id} ({boq.display_name}): {missing} of {len(lines)} lines would create a job.cost.line")
            else:
                created_count, result = boq._sync_job_cost_lines(strict=False)
                sheet_created += created_count
                print(f"  BOQ {boq.id} ({boq.display_name}): created {created_count}, {len(result)} total linked")
        if not DRY_RUN:
            env.cr.commit()
            total_created += sheet_created
            print(f"  -> committed sheet {sheet.id} ({sheet_created} created)")
    except Exception as e:
        env.cr.rollback()
        sheets_failed.append((sheet.id, sheet.name, str(e)))
        print(f"  !! FAILED sheet {sheet.id}: {e} - rolled back this sheet, continuing")

print(f"\n{len(boqs_done)} distinct BOQ(s) touched.")

if not DRY_RUN:
    print(f"Total created: {total_created}")
    if sheets_failed:
        print(f"\n{len(sheets_failed)} sheet(s) failed and were skipped:")
        for sid, sname, err in sheets_failed:
            print(f"  sheet {sid} '{sname}': {err}")
    else:
        print("No failures.")
else:
    print("Dry run only - set DRY_RUN = False and re-run to apply.")
