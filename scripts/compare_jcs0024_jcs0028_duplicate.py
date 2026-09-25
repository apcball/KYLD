# Read-only: JCS/0024/2026 and JCS/0028/2026 both point at project "Forest 2
# /B10" (id 171) and analytic_account_id 185, so their Actual Cost figures
# are identical/combined (see audit_jcs0028_labour_cost.py). Figure out
# which one is the real, actively-used sheet and which is a duplicate, using
# signals that are tied to the SHEET directly (not the shared analytic
# account): create_date/user, BOQ links, MR count, job_cost_line-linked
# PO/bill count, cost_lines_count, state.
#
# Usage (no writes):
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/compare_jcs0024_jcs0028_duplicate.py

JobCostSheet = env['job.cost.sheet'].sudo()
MR = env['material.requisition'].sudo()

for name in ['JCS/0024/2026', 'JCS/0028/2026']:
    s = JobCostSheet.search([('name', '=', name)], limit=1)
    print(f"\n=== {name} (sheet {s.id}) ===")
    print(f"  state={s.state}, create_date={s.create_date}, create_uid={s.create_uid.name}")
    print(f"  write_date={s.write_date}, write_uid={s.write_uid.name}")
    print(f"  sequence={s.sequence}, date_start={s.date_start}, date_end={s.date_end}")
    print(f"  cost_lines_count={s.cost_lines_count} (material={len(s.material_cost_ids)}, "
          f"labour={len(s.labour_cost_ids)}, overhead={len(s.overhead_cost_ids)})")
    print(f"  boq_ids: {[(b.id, b.display_name, b.state) for b in s.boq_ids]}")

    mrs = MR.search([('job_cost_sheet_id', '=', s.id)])
    print(f"  MRs linked (job_cost_sheet_id): {len(mrs)}")

    # PO/bill lines linked DIRECTLY via job_cost_line_id -> this sheet's cost lines
    all_cost_line_ids = (s.material_cost_ids | s.labour_cost_ids | s.overhead_cost_ids).ids
    if all_cost_line_ids:
        po_count = env['purchase.order.line'].sudo().search_count([('job_cost_line_id', 'in', all_cost_line_ids)])
        bill_count = env['account.move.line'].sudo().search_count([('job_cost_line_id', 'in', all_cost_line_ids)])
    else:
        po_count = bill_count = 0
    print(f"  PO lines directly linked via job_cost_line_id: {po_count}")
    print(f"  Bill lines directly linked via job_cost_line_id: {bill_count}")

    print(f"  boq_material_cost={s.boq_material_cost}, boq_labour_cost={s.boq_labour_cost}, boq_total_cost={s.boq_total_cost}")
    print(f"  total_material_cost={s.total_material_cost}, total_labour_cost={s.total_labour_cost}")

print("\n=== Project 171 itself ===")
Project = env['project.project'].sudo()
p = Project.browse(171)
print(f"  name={p.display_name}, analytic_account_id={p.analytic_account_id.id if p.analytic_account_id else None}, "
      f"active={p.active}, create_date={p.create_date}")
sheets_on_project = JobCostSheet.search([('project_id', '=', 171)])
print(f"  ALL job.cost.sheet rows for this project: {[(s.id, s.name, s.state) for s in sheets_on_project]}")
