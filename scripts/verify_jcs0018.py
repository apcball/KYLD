# Read-only verification of JCS/0018/2026 numbers shown in the UI screenshot
# (2026-09-12) against the DB: recompute material/labour/overhead totals
# directly from job.cost.line rows and compare to the sheet's stored
# computed fields, and check the project_id vs analytic_account_id mismatch
# visible in the screenshot (Project/Contract = "Forest 4 /KS10" but
# Analytic Account = "Forest 3 /KS10").
#
# Usage (no writes):
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/verify_jcs0018.py

JobCostSheet = env['job.cost.sheet'].sudo()

sheet = JobCostSheet.search([('name', '=', 'JCS/0018/2026')], limit=1)
print(f"Sheet {sheet.id} '{sheet.name}'")
print(f"  project_id           = {sheet.project_id.id, sheet.project_id.display_name}")
print(f"  analytic_account_id  = {sheet.analytic_account_id.id, sheet.analytic_account_id.display_name}")
if sheet.project_id.analytic_account_id:
    print(f"  project_id.analytic_account_id = {sheet.project_id.analytic_account_id.id, sheet.project_id.analytic_account_id.display_name}")
print(f"  MISMATCH: {sheet.project_id.display_name != sheet.analytic_account_id.display_name}")

print("\n--- Stored/displayed values ---")
for f in ['boq_material_cost', 'boq_labour_cost', 'boq_overhead_cost', 'boq_total_cost',
          'active_material_cost', 'total_labour_cost', 'total_overhead_cost', 'active_total_cost',
          'actual_material_cost', 'actual_labour_cost', 'actual_overhead_cost', 'actual_total_cost']:
    if f in sheet._fields:
        print(f"  {f} = {getattr(sheet, f)}")

print(f"\n  material_cost_ids count = {len(sheet.material_cost_ids)}")
print(f"  labour_cost_ids count   = {len(sheet.labour_cost_ids)}")
print(f"  overhead_cost_ids count = {len(sheet.overhead_cost_ids)}")

print("\n--- Recomputed directly from job.cost.line (sanity check) ---")
mat_actual = sum(sheet.material_cost_ids.mapped('actual_cost'))
lab_actual = sum(sheet.labour_cost_ids.mapped('actual_cost'))
ovh_actual = sum(sheet.overhead_cost_ids.mapped('actual_cost'))
print(f"  sum(material_cost_ids.actual_cost) = {mat_actual}")
print(f"  sum(labour_cost_ids.actual_cost)   = {lab_actual}")
print(f"  sum(overhead_cost_ids.actual_cost) = {ovh_actual}")
print(f"  sum total = {mat_actual + lab_actual + ovh_actual}")

mat_boq = sum(sheet.material_cost_ids.mapped('boq_total_cost'))
lab_boq = sum(sheet.labour_cost_ids.mapped('boq_total_cost'))
print(f"\n  sum(material_cost_ids.boq_total_cost) = {mat_boq}")
print(f"  sum(labour_cost_ids.boq_total_cost)   = {lab_boq}")

mat_active = sum(sheet.material_cost_ids.mapped('active_total_cost'))
lab_active = sum(sheet.labour_cost_ids.mapped('active_total_cost'))
print(f"\n  sum(material_cost_ids.active_total_cost) = {mat_active}")
print(f"  sum(labour_cost_ids.active_total_cost)   = {lab_active}")

print("\n--- Cross-check: any lines still mis-bucketed by code convention? ---")
def code(p):
    return (p.default_code or '').strip().upper()
bad_mat = sheet.material_cost_ids.filtered(lambda l: l.product_id and code(l.product_id).startswith('L'))
bad_lab = sheet.labour_cost_ids.filtered(lambda l: l.product_id and code(l.product_id).startswith('M'))
print(f"  material lines with 'L' code: {len(bad_mat)}")
print(f"  labour lines with 'M' code: {len(bad_lab)}")
