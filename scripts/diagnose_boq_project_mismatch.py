# Read-only diagnostic for the 9 job.cost.sheet ids that failed
# sync_all_unsynced_boqs.py's _sync_job_cost_lines(strict=False) call
# because boq.boq._check_work_context() rejected them:
#   - "job order and cost sheet must belong to the BOQ project"
#   - "project, job order and cost sheet must belong to the BOQ company"
# For each failed sheet, print the BOQ's project/job_order/company versus
# the cost sheet's own project/job_order/company so the actual mismatch
# is visible before deciding how to fix the data.
#
# Usage (read-only, no writes):
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/diagnose_boq_project_mismatch.py

SHEET_IDS = [58, 54, 33, 32, 26, 25, 24, 23, 15]

JobCostSheet = env['job.cost.sheet'].sudo()

for sheet in JobCostSheet.browse(SHEET_IDS):
    print(f"\n=== Sheet {sheet.id} '{sheet.name}' ===")
    print(f"  sheet.project_id   = {sheet.project_id.id, sheet.project_id.display_name}")
    print(f"  sheet.company_id   = {sheet.company_id.id, sheet.company_id.name}")
    for boq in sheet.boq_ids:
        print(f"  BOQ {boq.id} ({boq.display_name}):")
        print(f"    boq.project_id      = {boq.project_id.id, boq.project_id.display_name}")
        print(f"    boq.company_id      = {boq.company_id.id, boq.company_id.name}")
        print(f"    boq.job_order_id    = {(boq.job_order_id.id, boq.job_order_id.display_name) if boq.job_order_id else None}")
        if boq.job_order_id:
            print(f"      job_order.project_id = {boq.job_order_id.project_id.id, boq.job_order_id.project_id.display_name}")
            print(f"      job_order.company_id = {boq.job_order_id.company_id.id if boq.job_order_id.company_id else None}")
        print(f"    boq.job_cost_sheet_id = {(boq.job_cost_sheet_id.id, boq.job_cost_sheet_id.name) if boq.job_cost_sheet_id else None}")
        if boq.job_cost_sheet_id:
            print(f"      cost_sheet.project_id = {boq.job_cost_sheet_id.project_id.id, boq.job_cost_sheet_id.project_id.display_name}")
            print(f"      cost_sheet.company_id = {boq.job_cost_sheet_id.company_id.id, boq.job_cost_sheet_id.company_id.name}")
        mismatches = []
        if boq.company_id not in env.companies:
            mismatches.append('BOQ company not in allowed companies')
        for label, rec in (('project', boq.project_id), ('job_order', boq.job_order_id), ('cost_sheet', boq.job_cost_sheet_id)):
            if rec and rec.company_id and rec.company_id != boq.company_id:
                mismatches.append(f'{label}.company_id ({rec.company_id.name}) != boq.company_id ({boq.company_id.name})')
        for label, rec in (('job_order', boq.job_order_id), ('cost_sheet', boq.job_cost_sheet_id)):
            if rec and rec.project_id != boq.project_id:
                mismatches.append(f'{label}.project_id ({rec.project_id.display_name}) != boq.project_id ({boq.project_id.display_name})')
        print(f"    -> MISMATCH: {mismatches if mismatches else 'none found (check again / different cause)'}")
