# Read-only check for JCS/0034/2026: cost_type='material' lines whose
# product code starts with 'L' (labour convention) instead of 'M'
# (material convention), per user's definition:
#   material product: detailed_type='product' (storable), code starts with 'M'
#   labour product:    detailed_type='service', code starts with 'L'
#
# Usage (no writes):
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/check_jcs0034_material_cost_type.py

JobCostSheet = env['job.cost.sheet'].sudo()

sheet = JobCostSheet.search([('name', '=', 'JCS/0034/2026')], limit=1)
print(f"Sheet {sheet.id} '{sheet.name}' - project {sheet.project_id.display_name}")
print(f"{len(sheet.material_cost_ids)} material cost lines, {len(sheet.labour_cost_ids)} labour cost lines")

def code(p):
    return (p.default_code or '').strip().upper()

print("\n=== material cost_type lines whose product code starts with 'L' (labour code, wrong bucket) ===")
wrong = sheet.material_cost_ids.filtered(lambda l: l.product_id and code(l.product_id).startswith('L'))
for line in wrong:
    p = line.product_id
    print(f"  cost_line {line.id}: [{p.default_code}] {p.name or p.display_name} "
          f"(detailed_type={p.detailed_type}) planned_qty={line.planned_qty} actual_cost={line.actual_cost} "
          f"boq_line_id={line.boq_line_id.id or None}")
print(f"Total: {len(wrong)}")

print("\n=== labour cost_type lines whose product code starts with 'M' (material code, wrong bucket, sanity check) ===")
wrong2 = sheet.labour_cost_ids.filtered(lambda l: l.product_id and code(l.product_id).startswith('M'))
for line in wrong2:
    p = line.product_id
    print(f"  cost_line {line.id}: [{p.default_code}] {p.name or p.display_name} "
          f"(detailed_type={p.detailed_type}) planned_qty={line.planned_qty} actual_cost={line.actual_cost} "
          f"boq_line_id={line.boq_line_id.id or None}")
print(f"Total: {len(wrong2)}")

print("\n=== material cost_type lines whose product code neither starts with 'M' nor 'L' (other conventions, informational) ===")
other = sheet.material_cost_ids.filtered(lambda l: l.product_id and not code(l.product_id).startswith('M') and not code(l.product_id).startswith('L'))
from collections import Counter
prefixes = Counter(code(l.product_id)[:1] or '(none)' for l in other)
print(f"  {len(other)} lines, prefix breakdown: {dict(prefixes)}")

print("\n=== create_date of the wrong-bucket lines (were they from today's sync or pre-existing?) ===")
for line in wrong:
    print(f"  cost_line {line.id}: create_date={line.create_date}, boq_line_id={line.boq_line_id.id or None}")
