# Data fix for PROD: employee moved department (16 -> 55), PR.dept_id was a
# live `related` field so existing PRs followed the employee. Budget reservations
# of the POs stayed on the old department (16) while the vendor bill resolves
# its department via PR -> 55, which has no May-2026 allocation, so
# "Create Bill" failed:
#   APO2600923 APO2601085 APO2601086 APO2601172 APO2601202 APO2601203 APO2601204
#
# Run AFTER deploying employee_purchase_requisition (dept_id is now a snapshot)
# AND restarting the odoo container (Python change; -u alone is not enough).
#
# What it does: for each PO below, take PO.department_id (the department the
# budget was originally reserved on) as source of truth, restore it on the
# linked PR, PO.dept_id and PO lines that carry a different department, then
# rebuild the PO's budget.move 'reserved' rows.
#
# Usage (on the PROD host):
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/fix_pr_dept_after_employee_move.py
#
# DRY_RUN = True prints only (rolls back). Set False to apply + commit.

DRY_RUN = True

PO_NAMES = [
    'APO2600923', 'APO2601085', 'APO2601086', 'APO2601172',
    'APO2601202', 'APO2601203', 'APO2601204',
]

PR = env['employee.purchase.requisition'].sudo()
pos = env['purchase.order'].sudo().search([('name', 'in', PO_NAMES)])
print(f"Found {len(pos)}/{len(PO_NAMES)} POs")

for po in pos:
    target = po.department_id
    if not target:
        print(f"SKIP {po.name}: no department_id")
        continue
    pr_name = getattr(po, 'requisition_order', False) or getattr(po, 'pr_number', False)
    pr = PR.search([('name', '=', pr_name)], limit=1) if pr_name else PR
    bad_lines = po.order_line.filtered(lambda l: l.department_id and l.department_id != target)
    print(
        f"{po.name}: target dept={target.id} {target.name} | "
        f"PR {pr.name or '-'} dept={pr.dept_id.id or '-'} | "
        f"PO.dept_id={po.dept_id.id or '-'} | lines to fix={len(bad_lines)}"
    )
    if pr and pr.dept_id != target:
        pr.dept_id = target
    if po.dept_id != target:
        po.dept_id = target
    if bad_lines:
        bad_lines.write({'department_id': target.id})

# Rebuild reservations (PR moves, then PO moves)
prs = PR.search([('name', 'in', [
    getattr(p, 'requisition_order', False) or getattr(p, 'pr_number', False) for p in pos
] )])
if prs:
    prs._update_budget_moves()
pos._update_budget_moves()

moves = env['budget.move'].sudo().search([
    ('source_model', '=', 'purchase.order'), ('source_id', 'in', pos.ids)])
print(f"reserved rows after rebuild: {len(moves)}; by dept:",
      {d.id: len(moves.filtered(lambda m: m.department_id == d)) for d in moves.mapped('department_id')})

if DRY_RUN:
    env.cr.rollback()
    print("DRY_RUN: rolled back, nothing written.")
else:
    env.cr.commit()
    print("Committed.")
