# Consolidated, READ-ONLY data-reliability audit for job_costing_management
# on PROD (KYLD_LIVE) - covers every known bug class found while comparing
# code against live PROD data (see commits ae5e783, 9bdcad1, 00abdf1,
# d09206c, 940e2ff, fb2ff64, afe59b5 and scripts/*.py in this directory),
# plus a check of whether each prior fix's companion data-migration script
# was actually run against PROD.
#
# Makes NO writes. Any env.cr state touched by calling compute methods is
# rolled back at the end (env.cr.rollback()).
#
# Usage:
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/audit_prod_data_reliability_20260912.py
#
# Output: printed report only. Redirect to a file to keep it:
#   ... < scripts/audit_prod_data_reliability_20260912.py > /tmp/audit_out.txt

from collections import Counter, defaultdict

JobCostSheet = env['job.cost.sheet'].sudo()
JobCostLine = env['job.cost.line'].sudo()
POLine = env['purchase.order.line'].sudo()
BOQ = env['boq.boq'].sudo()
Project = env['project.project'].sudo()

issues = defaultdict(list)  # sheet_id -> list of issue strings

all_sheets = JobCostSheet.search([])
print(f"=== Auditing {len(all_sheets)} job.cost.sheet record(s) on {env.cr.dbname} ===\n")

# ---------------------------------------------------------------------------
# Check 1: cancelled BOQ still counted / stale stored totals (fixed 940e2ff,
# recompute script fb2ff64 - was it actually applied?)
# ---------------------------------------------------------------------------
print("--- Check 1: cancelled-BOQ totals + stale stored fields (fb2ff64 recompute) ---")
stale_count = 0
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
        stale_count += 1
        issues[sheet.id].append(
            f"STALE stored totals: boq {before[0]}->{after[0]}, active {before[1]}->{after[1]}, "
            f"total {before[2]}->{after[2]}, actual {before[3]}->{after[3]}, variance {before[4]}->{after[4]}"
        )
        print(f"  Sheet {sheet.id} '{sheet.name}': STALE - {before} -> {after}")
print(f"Result: {stale_count} of {len(all_sheets)} sheets have stale stored totals "
      f"(recompute script fb2ff64 {'was NOT fully applied' if stale_count else 'appears applied - all fresh'}).\n")

env.cr.rollback()  # undo any in-memory compute side effects before continuing

# ---------------------------------------------------------------------------
# Check 2: cost_type vs product-code mismatch (fixed 632 rows in d09206c;
# re-check for NEW mismatches since then)
# ---------------------------------------------------------------------------
print("--- Check 2: cost_type vs product-code (M/L) mismatch ---")

def code(p):
    return (p.default_code or '').strip().upper()

material_wrong = JobCostLine.search([('cost_type', '=', 'material')]).filtered(
    lambda l: l.product_id and code(l.product_id).startswith('L'))
labour_wrong = JobCostLine.search([('cost_type', '=', 'labour')]).filtered(
    lambda l: l.product_id and code(l.product_id).startswith('M'))
all_wrong = material_wrong | labour_wrong
print(f"material cost_type but 'L'-coded product: {len(material_wrong)}")
print(f"labour cost_type but 'M'-coded product: {len(labour_wrong)}")
for line in all_wrong:
    issues[line.cost_sheet_id.id].append(
        f"cost_type mismatch: cost_line {line.id} cost_type={line.cost_type} "
        f"product=[{line.product_id.default_code}] actual_cost={line.actual_cost}"
    )
print(f"Result: {len(all_wrong)} mismatched line(s) across {len({l.cost_sheet_id.id for l in all_wrong})} sheet(s) "
      f"(0 expected if d09206c's 632-row fix fully covers current state).\n")

# ---------------------------------------------------------------------------
# Check 3: PO line linked to WRONG job.cost.line via stale boq_line_id
# mismatch (fixed ae5e783; companion relink script f1cdc0a - was it run?)
# ---------------------------------------------------------------------------
print("--- Check 3: PO line -> job.cost.line boq_line_id mismatch (f1cdc0a relink) ---")
po_lines = POLine.search([('material_requisition_line_id', '!=', False)])
mismatches = []
for pol in po_lines:
    req_line = pol.material_requisition_line_id
    boq_line = req_line.boq_line_id
    if not boq_line:
        continue
    current = pol.job_cost_line_id
    if not current:
        continue
    if not current.boq_line_id or current.boq_line_id.id == boq_line.id:
        continue
    mismatches.append((pol, current, boq_line))
    issues[current.cost_sheet_id.id].append(
        f"PO/BOQ mismatch: PO line {pol.id} ({pol.order_id.name}) linked to cost_line {current.id} "
        f"(boq_line {current.boq_line_id.id}) but its own BOQ line is {boq_line.id}"
    )
print(f"Result: {len(mismatches)} PO line(s) still linked to a cost line whose boq_line_id disagrees "
      f"({'relink script appears NOT fully run' if mismatches else 'none found - relink appears complete or bug never recurred'}).\n")

# ---------------------------------------------------------------------------
# Check 4: multiple sheets sharing one analytic_account_id (afe59b5 -
# mitigated with UI warning only, not fixed; actuals grouped by account)
# ---------------------------------------------------------------------------
print("--- Check 4: sheets sharing one analytic_account_id (combined Actual Cost) ---")
by_account = defaultdict(list)
for sheet in all_sheets:
    if sheet.analytic_account_id:
        by_account[sheet.analytic_account_id.id].append(sheet)
shared = {aid: sheets for aid, sheets in by_account.items() if len(sheets) > 1}
print(f"Result: {len(shared)} analytic account(s) shared by 2+ sheets:")
for aid, sheets in shared.items():
    names = [s.name for s in sheets]
    print(f"  account {aid}: {names}")
    for s in sheets:
        issues[s.id].append(f"shares analytic_account_id {aid} with: {[n for n in names if n != s.name]}")
print()

# ---------------------------------------------------------------------------
# Check 5: duplicate job.cost.sheet per project (8 pairs found; only 2 empty
# ones cleaned up by cleanup_duplicate_empty_job_cost_sheets.py - unconfirmed run)
# ---------------------------------------------------------------------------
print("--- Check 5: duplicate job.cost.sheet records per project ---")
by_project = defaultdict(list)
for sheet in all_sheets:
    if sheet.project_id:
        by_project[sheet.project_id.id].append(sheet)
dup_projects = {pid: sheets for pid, sheets in by_project.items() if len(sheets) > 1}
print(f"Result: {len(dup_projects)} project(s) with 2+ job.cost.sheet records:")
for pid, sheets in dup_projects.items():
    proj = Project.browse(pid)
    for s in sheets:
        line_count = len(s.material_cost_ids | s.labour_cost_ids | s.overhead_cost_ids)
        empty = line_count == 0 and not s.boq_ids
        print(f"  project {pid} '{proj.display_name}': sheet {s.id} '{s.name}' state={s.state} "
              f"lines={line_count} boqs={len(s.boq_ids)}{' [EMPTY]' if empty else ''}")
        issues[s.id].append(f"duplicate sheet on project {pid} alongside {[x.name for x in sheets if x.id != s.id]}"
                             + (" [this copy is EMPTY - candidate for cleanup]" if empty else " [has real data - needs human decision]"))
print()

# ---------------------------------------------------------------------------
# Check 6: BOQ project/company mismatch (9 sheets flagged
# "not yet fixed" in pending_boq_project_company_mismatches_20260912.md)
# ---------------------------------------------------------------------------
print("--- Check 6: BOQ vs cost-sheet project/company mismatch ---")
mismatch_sheets = []
for sheet in all_sheets:
    for boq in sheet.boq_ids:
        reasons = []
        if boq.company_id not in env.companies:
            reasons.append('BOQ company not in allowed companies')
        for label, rec in (('project', boq.project_id), ('job_order', boq.job_order_id), ('cost_sheet', boq.job_cost_sheet_id)):
            if rec and rec.company_id and rec.company_id != boq.company_id:
                reasons.append(f'{label}.company_id != boq.company_id')
        for label, rec in (('job_order', boq.job_order_id), ('cost_sheet', boq.job_cost_sheet_id)):
            if rec and rec.project_id != boq.project_id:
                reasons.append(f'{label}.project_id != boq.project_id')
        if reasons:
            mismatch_sheets.append(sheet.id)
            issues[sheet.id].append(f"BOQ {boq.id} project/company mismatch: {reasons}")
print(f"Result: {len(set(mismatch_sheets))} sheet(s) have at least one BOQ with project/company mismatch "
      f"(baseline was 9 as of pending_boq_project_company_mismatches_20260912.md).\n")

# ---------------------------------------------------------------------------
# Check 7: sheet-level PO auto-link fallback (purchase_order.py ~L326-366) -
# matches by product_id+name with NO boq_line_id scoping, unlike the
# BOQ-project fallback fixed in ae5e783. Flag sheets where 2+ distinct
# boq_line_id values exist under the same product+name within one cost-type
# bucket - a collision risk for this fallback path.
# ---------------------------------------------------------------------------
print("--- Check 7: sheet-level fallback collision risk (product+name, no boq_line_id scope) ---")
risk_count = 0
for sheet in all_sheets:
    for bucket_name, bucket in (('material', sheet.material_cost_ids), ('labour', sheet.labour_cost_ids)):
        groups = defaultdict(set)
        for line in bucket:
            groups[(line.product_id.id, line.name)].add(line.boq_line_id.id or False)
        for (pid, name), boq_line_ids in groups.items():
            if len(boq_line_ids) > 1:
                risk_count += 1
                issues[sheet.id].append(
                    f"fallback collision risk ({bucket_name}): product {pid} name={name!r} "
                    f"spans boq_line_ids {boq_line_ids} - sheet-level PO fallback could pick the wrong one"
                )
print(f"Result: {risk_count} product+name group(s) with ambiguous boq_line_id across sheets "
      f"(each is a latent collision risk for the un-scoped fallback at purchase_order.py ~L343-345).\n")

# ---------------------------------------------------------------------------
# Check 8: dashboard vs sheet consistency - executive_dashboard reads the
# SAME stored fields as the sheet (search_read, no independent compute), so
# a mismatch here would only happen if dashboard caching/stale search_read
# diverges from a fresh browse - sanity-check a sample.
# ---------------------------------------------------------------------------
print("--- Check 8: dashboard vs sheet stored-field consistency (spot check) ---")
dashboard_rows = JobCostSheet.search_read([], ['name', 'boq_total_cost', 'actual_total_cost', 'active_total_cost'])
mismatch8 = 0
for row in dashboard_rows:
    sheet = JobCostSheet.browse(row['id'])
    if (row['boq_total_cost'], row['actual_total_cost'], row['active_total_cost']) != \
       (sheet.boq_total_cost, sheet.actual_total_cost, sheet.active_total_cost):
        mismatch8 += 1
        issues[sheet.id].append("dashboard search_read value differs from sheet.browse() value")
print(f"Result: {mismatch8} sheet(s) where dashboard's search_read diverges from a fresh browse() "
      f"(expected 0 - dashboard has no independent computation, so any nonzero here means a caching bug).\n")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("=" * 78)
print("SUMMARY - per-sheet confidence rating")
print("=" * 78)
ok_count = suspect_count = 0
for sheet in all_sheets.sorted('name'):
    sheet_issues = issues.get(sheet.id, [])
    if not sheet_issues:
        ok_count += 1
        continue
    suspect_count += 1
    print(f"\n[SUSPECT] {sheet.name} (id={sheet.id}) - {len(sheet_issues)} issue(s):")
    for i in sheet_issues:
        print(f"    - {i}")

print(f"\n{'-' * 78}")
print(f"TOTAL: {len(all_sheets)} sheets | OK: {ok_count} | SUSPECT (>=1 open issue): {suspect_count}")
print(f"{'-' * 78}")

env.cr.rollback()
print("\n(rolled back any in-memory compute side effects - no data changed)")
