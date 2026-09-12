# Sync missing job.cost.line records for BOQs behind the 48 PO lines that
# fix_po_boq_line_mismatch.py (2026-09-12) had to skip because the expected
# boq_line had no job.cost.line yet. Mirrors what the "Create Job Cost Lines"
# button on a BOQ form does (boq.boq.action_create_job_cost_lines /
# _sync_job_cost_lines), run in bulk for every affected BOQ.
#
# Usage:
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/sync_missing_boq_cost_lines.py
#
# DRY_RUN = True: only reports which BOQs would be synced and how many lines
# each is missing. No writes, no commit.

DRY_RUN = True

BOQ_LINE_IDS = [
    7928, 7991, 12655, 12621, 12622, 12440, 10487, 10387,
    10345, 10346, 10347, 10348, 10349, 10350, 10351, 10352, 10353, 10354, 10355, 10356, 10357,
    10257, 10258, 10080, 10081, 10082, 9974, 9150, 9998, 9994, 9937, 9789, 9419, 9277, 9250,
    8718, 8858, 8717, 8328, 7532, 7608, 7563, 3973, 3979, 4006, 6647, 4008,
]

BoqLine = env['boq.line'].sudo()
Boq = env['boq.boq'].sudo()

lines = BoqLine.browse(BOQ_LINE_IDS).exists()
missing = lines.ids and set(BOQ_LINE_IDS) - set(lines.ids)
if missing:
    print(f"WARNING: {len(missing)} boq_line ids no longer exist: {sorted(missing)}")

boq_ids = lines.mapped('boq_id')
print(f"{len(lines)} boq.line records -> {len(boq_ids)} distinct BOQ(s)")

for boq in boq_ids:
    lines_here = lines.filtered(lambda l: l.boq_id.id == boq.id)
    print(f"\nBOQ {boq.id} ({boq.display_name}) - job_cost_sheet_id={boq.job_cost_sheet_id.id or None}, "
          f"{len(lines_here)} of the 48 target lines here")
    if not boq.job_cost_sheet_id:
        print("  SKIP: no job_cost_sheet_id on this BOQ - can't sync, needs manual linking first.")
        continue
    if DRY_RUN:
        would_create = 0
        for line in lines_here:
            existing = line._get_cost_line(boq.job_cost_sheet_id)
            if not existing:
                would_create += 1
        print(f"  DRY RUN: would create {would_create} job.cost.line(s) for this BOQ "
              f"(action runs against ALL product lines on the BOQ, not just these {len(lines_here)})")
    else:
        created_count, result = boq._sync_job_cost_lines(strict=False)
        print(f"  Created {created_count} job.cost.line(s); {len(result)} total linked after sync.")

if not DRY_RUN:
    env.cr.commit()
    print("\nCommitted.")
else:
    print("\nDry run only - set DRY_RUN = False and re-run to apply.")
