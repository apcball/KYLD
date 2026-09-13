# Post-fix recompute for PROD (job_costing_management): after the
# _compute_active_planned_qty fix (Scenario 2 now excludes MR lines already
# tied to a boq_line_id, job_cost_sheet.py commit <pending>), stored
# active_planned_qty / active_total_cost values on existing job.cost.line
# rows are stale - the compute method's own code changed, not its
# @api.depends fields, so Odoo won't auto-recompute on module update.
#
# Scoped to the 30 sheets confirmed affected by the MR-qty-double-counting
# bug (audit query: orphan line with >=2 BOQ-linked siblings for the same
# product on the same sheet, active_planned_qty != planned_qty).
#
# Usage (PROD host):
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/recompute_active_planned_qty_affected_sheets.py

AFFECTED_SHEET_NAMES = [
    'JCS/0042/2026', 'JCS/0048/2026', 'JCS/0038/2026', 'JCS/0017/2026',
    'JCS/0016/2026', 'JCS/0034/2026', 'JCS/0001/2025', 'JCS/0019/2026',
    'JCS/0022/2026', 'JCS/0021/2026', 'JCS/0020/2026', 'JCS/0018/2026',
    'JCS/0004/2025', 'JCS/0039/2026', 'JCS/0027/2026', 'JCS/0008/2025',
    'JCS/0006/2025', 'JCS/0007/2025', 'JCS/0002/2025', 'JCS/0010/2025',
    'JCS/0005/2025', 'JCS/0009/2025', 'JCS/0011/2025', 'JCS/0056/2026',
    'JCS/0059/2026', 'JCS/0014/2025', 'JCS/0036/2026', 'JCS/0030/2026',
    'JCS/0028/2026', 'JCS/0029/2026', 'JCS/0047/2026',
]

Sheet = env['job.cost.sheet'].sudo()
Line = env['job.cost.line'].sudo()

sheets = Sheet.search([('name', 'in', AFFECTED_SHEET_NAMES)])
print(f"Found {len(sheets)}/{len(AFFECTED_SHEET_NAMES)} sheets")

before = {s.id: (s.name, s.boq_total_cost, s.active_total_cost) for s in sheets}

lines = Line.search([('cost_sheet_id', 'in', sheets.ids)])
lines._compute_active_planned_qty()
lines._compute_active_total_cost()
sheets._compute_active_totals()
sheets._compute_boq_totals()
env.cr.commit()

print("\n=== Recomputed and committed ===")
for s in sheets:
    name, budget_before, active_before = before[s.id]
    print(f"{name}: Budget {budget_before:.2f} -> {s.boq_total_cost:.2f} | "
          f"Active {active_before:.2f} -> {s.active_total_cost:.2f}")
