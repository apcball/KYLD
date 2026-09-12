# Read-only deep audit of JCS/0018/2026's MR -> PO -> Bill chain to check
# whether the Actual Cost numbers shown on the dashboard are trustworthy,
# given the confirmed project/analytic_account mismatch (project 97
# "Forest 4 /KS10" is linked to analytic_account_id 98, whose display_name
# reads "Forest 3 /KS10").
#
# Checks:
#  1. Is there a genuinely separate project actually named "Forest 3 /KS10"
#     that might share analytic_account 98 and bleed its PO/bill costs into
#     this sheet's Actual Cost total (or vice versa)?
#  2. Material Requisitions linked to this sheet - do they match its BOQ?
#  3. PO lines whose analytic_distribution key is '98' - do they look like
#     they belong to this project (partner/description), and are there PO
#     lines that get picked up ONLY via the job_cost_line fallback branch
#     (no analytic_distribution at all)?
#  4. Posted bills matched the same way.
#  5. Cross-check: sum PO+bill+timesheet contributions manually per bucket
#     and compare to the sheet's stored actual_* fields.
#
# Usage (no writes):
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/audit_jcs0018_mr_po_bill.py

JobCostSheet = env['job.cost.sheet'].sudo()
Project = env['project.project'].sudo()
MR = env['material.requisition'].sudo()

sheet = JobCostSheet.search([('name', '=', 'JCS/0018/2026')], limit=1)
account_id = sheet.analytic_account_id.id
print(f"Sheet {sheet.id} '{sheet.name}', project={sheet.project_id.display_name} (id {sheet.project_id.id}), "
      f"analytic_account_id={account_id} ({sheet.analytic_account_id.display_name})")

print("\n=== 1. Any other project also named like 'Forest 3' or sharing this analytic account? ===")
similar_projects = Project.search([('name', 'ilike', 'Forest 3 /KS10')])
for p in similar_projects:
    print(f"  project {p.id} '{p.display_name}' analytic_account_id={p.analytic_account_id.id if p.analytic_account_id else None}")
other_sheets_same_account = JobCostSheet.search([('analytic_account_id', '=', account_id)])
print(f"  job.cost.sheet rows using analytic_account_id={account_id}: {[(s.id, s.name) for s in other_sheets_same_account]}")

print("\n=== 2. Material Requisitions linked to this sheet ===")
mrs = MR.search([('job_cost_sheet_id', '=', sheet.id)])
print(f"  {len(mrs)} MRs linked to sheet {sheet.id}")
for mr in mrs[:20]:
    print(f"  MR {mr.id} {mr.name if hasattr(mr, 'name') else ''} state={mr.state if hasattr(mr, 'state') else '?'} "
          f"boq_id={mr.boq_id.id if hasattr(mr, 'boq_id') and mr.boq_id else None}")
if len(mrs) > 20:
    print(f"  ... and {len(mrs) - 20} more")

print("\n=== 3. PO lines with analytic_distribution key matching account_id (direct match, branch 1) ===")
env.cr.execute("""
    SELECT pol.id, po.name, po.state, pol.product_id, pt.default_code, pt.detailed_type,
           pol.price_subtotal, pol.qty_received, pol.product_qty, res_partner.name AS vendor
    FROM purchase_order_line pol
    JOIN purchase_order po ON po.id = pol.order_id
    LEFT JOIN res_partner ON res_partner.id = po.partner_id
    LEFT JOIN product_product pp ON pp.id = pol.product_id
    LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
    JOIN jsonb_each_text(COALESCE(pol.analytic_distribution, '{}'::jsonb)) AS kv(key, value) ON TRUE
    WHERE kv.key ~ ('(^|,)' || %(aid)s || '(,|$)')
      AND po.state IN ('purchase', 'done')
      AND pol.display_type IS NULL
""", {'aid': account_id})
rows = env.cr.fetchall()
print(f"  {len(rows)} PO line(s) directly distributed to this account")
for r in rows:
    print(f"  POL {r[0]} PO={r[1]} state={r[2]} product_code={r[4]} type={r[5]} price_subtotal={r[6]} vendor={r[9]}")

print("\n=== 4. PO lines picked up via job_cost_line fallback (branch 2 - no analytic_distribution) ===")
env.cr.execute("""
    SELECT pol.id, po.name, po.state, jcl.id AS cost_line_id, jcl.cost_type, jcl.cost_sheet_id,
           pt.default_code, pol.price_subtotal
    FROM purchase_order_line pol
    JOIN purchase_order po ON po.id = pol.order_id
    JOIN job_cost_line jcl ON jcl.id = pol.job_cost_line_id
    JOIN job_cost_sheet jcs ON jcs.id = jcl.cost_sheet_id
    LEFT JOIN product_product pp ON pp.id = pol.product_id
    LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
    WHERE jcs.analytic_account_id = %(aid)s
      AND po.state IN ('purchase', 'done')
      AND pol.display_type IS NULL
      AND NOT EXISTS (
          SELECT 1 FROM jsonb_object_keys(COALESCE(pol.analytic_distribution, '{}'::jsonb)) k
          WHERE k ~ ('(^|,)' || %(aid)s || '(,|$)')
      )
""", {'aid': account_id})
rows2 = env.cr.fetchall()
print(f"  {len(rows2)} PO line(s) picked up via fallback (job_cost_line -> cost_sheet -> analytic_account)")
for r in rows2:
    print(f"  POL {r[0]} PO={r[1]} state={r[2]} cost_line={r[3]} cost_type={r[4]} cost_sheet_id={r[5]} product_code={r[6]} price_subtotal={r[7]}")
    if r[5] != sheet.id:
        print(f"    ^^ NOTE: this cost_line belongs to a DIFFERENT sheet (id {r[5]}) that happens to share this analytic_account")

print("\n=== 5. Posted bills matched to this account ===")
env.cr.execute("""
    SELECT aml.id, am.name, am.move_type, aml.balance, pt.default_code, res_partner.name
    FROM account_move_line aml
    JOIN account_move am ON am.id = aml.move_id
    LEFT JOIN res_partner ON res_partner.id = am.partner_id
    LEFT JOIN product_product pp ON pp.id = aml.product_id
    LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
    JOIN jsonb_each_text(COALESCE(aml.analytic_distribution, '{}'::jsonb)) AS kv(key, value) ON TRUE
    WHERE kv.key ~ ('(^|,)' || %(aid)s || '(,|$)')
      AND am.state = 'posted' AND am.move_type IN ('in_invoice', 'in_refund')
      AND aml.display_type = 'product'
""", {'aid': account_id})
rows3 = env.cr.fetchall()
print(f"  {len(rows3)} bill line(s) directly distributed to this account")
for r in rows3:
    print(f"  AML {r[0]} bill={r[1]} type={r[2]} balance={r[3]} product_code={r[4]} vendor={r[5]}")

print("\n=== 6. Manual recompute vs stored field ===")
totals = sheet._get_analytic_actual_cost_totals([account_id])
print(f"  fresh _get_analytic_actual_cost_totals([{account_id}]) = {totals.get(account_id)}")
print(f"  stored actual_material_cost={sheet.actual_material_cost}, actual_labour_cost={sheet.actual_labour_cost}, "
      f"actual_overhead_cost={sheet.actual_overhead_cost}")
