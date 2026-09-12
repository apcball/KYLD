# Read-only, whole-DB version of check_jcs0034_material_cost_type.py.
# Scans every job.cost.line (not just JCS/0034/2026) for cost_type vs
# product-code mismatch per the user's convention:
#   material product: code starts with 'M' (storable)
#   labour product:   code starts with 'L' (service)
#
# Usage (no writes):
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/check_all_cost_type_mismatch.py

JobCostLine = env['job.cost.line'].sudo()

def code(p):
    return (p.default_code or '').strip().upper()

material_wrong = JobCostLine.search([('cost_type', '=', 'material')]).filtered(
    lambda l: l.product_id and code(l.product_id).startswith('L'))
labour_wrong = JobCostLine.search([('cost_type', '=', 'labour')]).filtered(
    lambda l: l.product_id and code(l.product_id).startswith('M'))

print(f"material cost_type but 'L'-coded product: {len(material_wrong)} lines")
print(f"labour cost_type but 'M'-coded product: {len(labour_wrong)} lines")

from collections import Counter
by_sheet = Counter(l.cost_sheet_id.name for l in material_wrong)
print(f"\nmaterial-wrong by sheet ({len(by_sheet)} sheets affected):")
for name, count in sorted(by_sheet.items(), key=lambda x: -x[1]):
    print(f"  {name}: {count}")

by_sheet2 = Counter(l.cost_sheet_id.name for l in labour_wrong)
print(f"\nlabour-wrong by sheet ({len(by_sheet2)} sheets affected):")
for name, count in sorted(by_sheet2.items(), key=lambda x: -x[1]):
    print(f"  {name}: {count}")

by_date = Counter(l.create_date.date() for l in (material_wrong | labour_wrong))
print(f"\nby create_date (all {len(material_wrong) + len(labour_wrong)} suspect lines):")
for d, count in sorted(by_date.items()):
    print(f"  {d}: {count}")

nonzero_actual = (material_wrong | labour_wrong).filtered(lambda l: l.actual_cost)
print(f"\n{len(nonzero_actual)} of the suspect lines have non-zero actual_cost (higher-impact):")
for line in nonzero_actual:
    p = line.product_id
    print(f"  sheet '{line.cost_sheet_id.name}' cost_line {line.id} cost_type={line.cost_type}: "
          f"[{p.default_code}] {p.name or p.display_name} actual_cost={line.actual_cost}")
