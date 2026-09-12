# Data fix for PROD (job_costing_management): remove genuinely-empty
# duplicate job.cost.sheet records.
#
# Found while investigating the Blue zone/A21 cost-tracking gap
# (2026-09-12): 8 projects each have 2 job_cost_sheet records. Checked all
# 8 pairs for real linked data (job.cost.line, boq.boq, purchase.order,
# purchase.order.line, material.requisition, purchase.allocation,
# account.move, chatter) before touching anything:
#
#   - 6 pairs both carry real data on BOTH sheets - NOT safe to auto-merge,
#     left untouched, needs a human decision (which sheet is authoritative,
#     or whether cost lines need manual merging).
#   - 2 pairs have one sheet with ZERO references anywhere (project 172's
#     JCS/0043 = sheet id 43, project 290's JCS/0057 = sheet id 57) next to
#     a sibling sheet with real data (JCS/0044, JCS/0060). Only chatter
#     (mail.message/mail.followers) existed on 43/57, which unlink() cleans
#     up automatically.
#
# This script only touches those 2 confirmed-empty sheets (ids 43, 57).
# Defaults to DRY_RUN = True (prints only, no writes/unlink).
#
# Usage (on the PROD host, after code fixes are already deployed):
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/cleanup_duplicate_empty_job_cost_sheets.py

DRY_RUN = True

EMPTY_SHEET_IDS = [43, 57]

JobCostSheet = env['job.cost.sheet'].sudo()
JobCostLine = env['job.cost.line'].sudo()
BOQ = env['boq.boq'].sudo()
MaterialRequisition = env['material.requisition'].sudo()
PurchaseAllocation = env['purchase.allocation'].sudo()
PurchaseOrder = env['purchase.order'].sudo()
PurchaseOrderLine = env['purchase.order.line'].sudo()
AccountMove = env['account.move'].sudo()

sheets = JobCostSheet.browse(EMPTY_SHEET_IDS).exists()
print(f"Found {len(sheets)} of {len(EMPTY_SHEET_IDS)} target sheets: {sheets.mapped('name')}")

blocked = []
for sheet in sheets:
    refs = {
        'job.cost.line': JobCostLine.search_count([('cost_sheet_id', '=', sheet.id)]),
        'boq.boq': BOQ.search_count([('job_cost_sheet_id', '=', sheet.id)]),
        'material.requisition': MaterialRequisition.search_count([('job_cost_sheet_id', '=', sheet.id)]),
        'purchase.allocation': PurchaseAllocation.search_count([('job_cost_sheet_id', '=', sheet.id)]),
        'purchase.order': PurchaseOrder.search_count([('job_cost_sheet_id', '=', sheet.id)]),
        'purchase.order.line': PurchaseOrderLine.search_count([('job_cost_sheet_id', '=', sheet.id)]),
        'account.move': AccountMove.search_count([('job_cost_sheet_id', '=', sheet.id)]),
    }
    nonzero = {k: v for k, v in refs.items() if v}
    if nonzero:
        blocked.append((sheet.id, sheet.name, nonzero))
    else:
        print(f"  {sheet.name} (id={sheet.id}, project={sheet.project_id.name}): confirmed empty, safe to remove")

if blocked:
    print("\nABORTING - some target sheets are NOT empty (re-verify before running again):")
    for sheet_id, name, nonzero in blocked:
        print(f"  {name} (id={sheet_id}): {nonzero}")
else:
    if DRY_RUN:
        print("\nDry run only - no records deleted. Set DRY_RUN = False and re-run to actually unlink.")
    else:
        sheets.unlink()
        env.cr.commit()
        print(f"\nDeleted {len(sheets)} empty duplicate job cost sheet(s). Committed.")
