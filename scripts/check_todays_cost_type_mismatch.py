# Read-only: of the 632 cost_type/product-code mismatches found DB-wide,
# isolate the ones created today (2026-09-12, from sync_missing_boq_cost_lines.py
# and sync_all_unsynced_boqs.py) and check WHY they're mismatched:
#   - if product.detailed_type == 'service': _sync_job_cost_lines's own logic
#     (cost_type = 'labour' if detailed_type=='service' else 'material')
#     would have set cost_type='labour' - so if we see 'material' here, our
#     sync script has a bug (or something else touched these lines after).
#   - if product.detailed_type != 'service' (e.g. 'product'): the sync logic
#     correctly filed it under 'material' by ITS OWN rule; the mismatch is
#     really a pre-existing product-master-data problem (product coded 'L'
#     but not typed as a service product), not a sync-script bug.
#
# Usage (no writes):
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/check_todays_cost_type_mismatch.py

import datetime
JobCostLine = env['job.cost.line'].sudo()

def code(p):
    return (p.default_code or '').strip().upper()

today_lines = JobCostLine.search([
    ('create_date', '>=', datetime.datetime(2026, 9, 12, 0, 0, 0)),
])
print(f"{len(today_lines)} job.cost.line rows created today total")

mat_wrong = today_lines.filtered(lambda l: l.cost_type == 'material' and l.product_id and code(l.product_id).startswith('L'))
lab_wrong = today_lines.filtered(lambda l: l.cost_type == 'labour' and l.product_id and code(l.product_id).startswith('M'))
print(f"Of today's rows: {len(mat_wrong)} material/L-coded, {len(lab_wrong)} labour/M-coded")

print("\n=== material/L-coded rows created today: sync logic vs product master data ===")
sync_bug = []
data_issue = []
for line in mat_wrong:
    p = line.product_id
    if p.detailed_type == 'service':
        sync_bug.append(line)
    else:
        data_issue.append(line)

print(f"\n{len(sync_bug)} rows where product.detailed_type='service' but cost_type ended up 'material' "
      f"(sync logic should have set labour - possible script/logic bug):")
for line in sync_bug:
    p = line.product_id
    print(f"  cost_line {line.id} sheet '{line.cost_sheet_id.name}' boq_line_id={line.boq_line_id.id if line.boq_line_id else None}: "
          f"[{p.default_code}] {p.name or p.display_name} detailed_type={p.detailed_type} create_date={line.create_date}")

print(f"\n{len(data_issue)} rows where product.detailed_type != 'service' "
      f"(sync logic correctly followed ITS OWN rule; the product master data itself is miscoded, pre-existing issue):")
for line in data_issue:
    p = line.product_id
    print(f"  cost_line {line.id} sheet '{line.cost_sheet_id.name}' boq_line_id={line.boq_line_id.id if line.boq_line_id else None}: "
          f"[{p.default_code}] {p.name or p.display_name} detailed_type={p.detailed_type} create_date={line.create_date}")

print("\n=== labour/M-coded rows created today ===")
for line in lab_wrong:
    p = line.product_id
    print(f"  cost_line {line.id} sheet '{line.cost_sheet_id.name}' boq_line_id={line.boq_line_id.id if line.boq_line_id else None}: "
          f"[{p.default_code}] {p.name or p.display_name} detailed_type={p.detailed_type} create_date={line.create_date}")
