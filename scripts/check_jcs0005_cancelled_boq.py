# Read-only check for JCS/0005/2025: confirm the reported bug - a
# cancelled BOQ's baseline budget still counts toward the sheet's
# BOQ Costs total, because boq.boq.action_cancel() only flips `state`
# and never touches the job.cost.line rows already created from it
# (boq.py action_cancel, line 201-202: self.write({'state': 'cancelled'})).
#
# Usage (no writes):
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/check_jcs0005_cancelled_boq.py

JobCostSheet = env['job.cost.sheet'].sudo()

sheet = JobCostSheet.search([('name', '=', 'JCS/0005/2025')], limit=1)
print(f"Sheet {sheet.id} '{sheet.name}' - {len(sheet.boq_ids)} BOQ(s)")
for boq in sheet.boq_ids:
    print(f"  BOQ {boq.id} ({boq.display_name}) state={boq.state}, total_cost={boq.total_cost if hasattr(boq, 'total_cost') else '?'}, "
          f"{len(boq.line_ids)} lines")

print(f"\nSheet boq_material_cost={sheet.boq_material_cost}, boq_labour_cost={sheet.boq_labour_cost}, boq_total_cost={sheet.boq_total_cost}")

print("\n=== job.cost.line rows whose boq_line_id belongs to a CANCELLED BOQ ===")
cancelled_boqs = sheet.boq_ids.filtered(lambda b: b.state == 'cancelled')
print(f"cancelled BOQ ids: {cancelled_boqs.ids}")

all_lines = sheet.material_cost_ids | sheet.labour_cost_ids | sheet.overhead_cost_ids
from_cancelled = all_lines.filtered(lambda l: l.boq_line_id and l.boq_line_id.boq_id.id in cancelled_boqs.ids)
print(f"{len(from_cancelled)} cost line(s) still linked to a cancelled BOQ's line, still counted in totals:")
sum_boq_total = sum(from_cancelled.mapped('boq_total_cost'))
print(f"  sum(boq_total_cost) of these = {sum_boq_total} (this amount is inflating BOQ Costs baseline budget)")
for line in from_cancelled[:15]:
    print(f"  cost_line {line.id} cost_type={line.cost_type} boq_total_cost={line.boq_total_cost} "
          f"product=[{line.product_id.default_code}] {line.product_id.name or line.product_id.display_name}")
if len(from_cancelled) > 15:
    print(f"  ... and {len(from_cancelled) - 15} more")
