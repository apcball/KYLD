# Flip cost_type on the job.cost.line rows found by
# scripts/check_all_cost_type_mismatch.py where cost_type disagrees with the
# product code convention (L=labour, M=material). See
# scripts/cost_type_mismatch_findings_20260912.md for the investigation.
#
# This does NOT touch product master data (that's
# scripts/fix_product_detailed_type.py, already applied for M0001542 only -
# the other 5 'L'-coded products still need inventory/accounting sign-off
# before their detailed_type can change, since they have real stock
# qty/move history).
#
# Usage:
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/fix_cost_type_mismatch.py
#
# DRY_RUN = True: only lists what would change, per sheet, with actual_cost
# shown so higher-impact rows are visible. No writes, no commit.
#
# DRY_RUN = False: applies and commits ONE JOB COST SHEET AT A TIME (like
# sync_all_unsynced_boqs.py) so a failure partway through doesn't lose
# already-applied sheets, and recomputes each sheet's actual-cost totals
# after its lines are flipped (cost_type isn't in _compute_actual_costs's
# @api.depends, so it won't recompute on its own).

DRY_RUN = True

JobCostLine = env['job.cost.line'].sudo()

def code(p):
    return (p.default_code or '').strip().upper()

material_wrong = JobCostLine.search([('cost_type', '=', 'material')]).filtered(
    lambda l: l.product_id and code(l.product_id).startswith('L'))
labour_wrong = JobCostLine.search([('cost_type', '=', 'labour')]).filtered(
    lambda l: l.product_id and code(l.product_id).startswith('M'))

all_wrong = material_wrong | labour_wrong
print(f"{len(material_wrong)} material->labour, {len(labour_wrong)} labour->material, {len(all_wrong)} total")

by_sheet = {}
for line in all_wrong:
    by_sheet.setdefault(line.cost_sheet_id, []).append(line)

print(f"{len(by_sheet)} sheets affected\n")

sheets_failed = []
total_applied = 0

for sheet, lines in sorted(by_sheet.items(), key=lambda kv: kv[0].id):
    print(f"Sheet {sheet.id} '{sheet.name}' - {len(lines)} line(s)")
    for line in lines:
        p = line.product_id
        new_type = 'labour' if line.cost_type == 'material' else 'material'
        flag = ' [ACTUAL_COST != 0]' if line.actual_cost else ''
        print(f"  cost_line {line.id}: [{p.default_code}] {p.name or p.display_name} "
              f"cost_type {line.cost_type} -> {new_type}, actual_cost={line.actual_cost}{flag}")
    if not DRY_RUN:
        try:
            for line in lines:
                new_type = 'labour' if line.cost_type == 'material' else 'material'
                line.write({'cost_type': new_type})
            sheet._compute_actual_costs()
            env.cr.commit()
            total_applied += len(lines)
            print(f"  -> committed ({len(lines)} line(s) flipped, sheet totals recomputed)")
        except Exception as e:
            env.cr.rollback()
            sheets_failed.append((sheet.id, sheet.name, str(e)))
            print(f"  !! FAILED sheet {sheet.id}: {e} - rolled back this sheet, continuing")
    print()

if not DRY_RUN:
    print(f"Total lines flipped: {total_applied}")
    if sheets_failed:
        print(f"{len(sheets_failed)} sheet(s) failed:")
        for sid, sname, err in sheets_failed:
            print(f"  sheet {sid} '{sname}': {err}")
else:
    print("Dry run only - set DRY_RUN = False and re-run to apply.")
